import csv
from datetime import datetime, timezone
import io
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
from app.auth.dependencies import get_current_user, require_admin, verify_api_version
from app.middleware.rate_limit import limiter
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session
from app.helper.helper import determin_age_group
from app.schama.profile import ProfileCreate
from app.database.database import get_db, engine, Base
from app.database.model import Profile, User, generate_uuid7
from app.utils.natural_lang import NaturalLanguageParser
from app.helper.validate_query import validate_query_parameters

router = APIRouter(prefix="/api/profiles", tags=["profiles"])

## create profile
@router.post("", status_code=201)
@limiter.limit("60/minute")
async def create_profile(
    request: Request,
    profile: ProfileCreate,
    api_version: bool = Depends(verify_api_version),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):

    if not profile.name or profile.name.strip() == "":
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Missing or empty name"},
        )
    if not isinstance(profile.name, str):
        return JSONResponse(
            status_code=422,
            content={"status": "error", "message": "Name must be a String"},
        )

    normalized_name = profile.name.strip().lower()

    existing_profile = db.query(Profile).filter(Profile.name == normalized_name).first()

    if existing_profile:
        return {
            "status": "success",
            "message": "Profile already exists",
            "data": {
                "id": profile.id,
                "name": profile.name,
                "gender": profile.gender,
                "gender_probability": profile.gender_probability,
                "age": profile.age,
                "age_group": profile.age_group,
                "country_id": profile.country_id,
                "country_name": profile.country_name,
                "country_probability": profile.country_probability,
                "created_at": profile.created_at.isoformat().replace("+00:00", "Z"),
            },
        }
    try:
        # gender_task = call_genderize(normalized_name)
        # age_task = call_agify(normalized_name)
        # country_task = call_nationalize(normalized_name)

        # gender_data, age_data, country_data = await asyncio.gather(
        #     gender_task, age_task, country_task
        # )
        with httpx.Client(timeout=10.0) as client:
            # Gendarize
            g_response = client.get(
                "https://api.genderize.io", params={"name": normalized_name}
            )

            g_data = g_response.json()

            # Agify
            a_response = client.get(
                "https://api.agify.io", params={"name": normalized_name}
            )
            a_data = a_response.json()

            # Nationalize
            n_response = client.get(
                "https://api.nationalize.io", params={"name": normalized_name}
            )
            n_data = n_response.json()
            # Validate responses
        if g_data.get("gender") is None or g_data.get("count") == 0:
            return JSONResponse(
                status_code=502,
                content={
                    "status": "502",
                    "message": "Genderize returned an invalid response",
                },
            )
        if a_data.get("age") is None:
            return JSONResponse(
                status_code=502,
                content={
                    "status": "502",
                    "message": "Agify returned an invalid response",
                },
            )

        if not n_data.get("country") or len(n_data["country"]) == 0:
            return JSONResponse(
                status_code=502,
                content={
                    "status": "502",
                    "message": "Nationalize returned an invalid response",
                },
            )

        # Get top country
        top_country = max(n_data["country"], key=lambda x: x["probability"])

        profile_id = generate_uuid7()
        new_profile = Profile(
            id=profile_id,
            name=normalized_name,
            created_by=current_user.id,
            gender=g_data["gender"],
            gender_probability=g_data["probability"],
            age=a_data["age"],
            age_group=determin_age_group(a_data["age"]),
            country_id=top_country["country_id"],
            country_probability=top_country["probability"],
            created_at=datetime.now(timezone.utc),
        )
        db.add(new_profile)
        db.commit()
        db.refresh(new_profile)

        return {
            "status": "success",
            "data": {
                "id": new_profile.id,
                "name": new_profile.name,
                "gender": new_profile.gender,
                "gender_probability": new_profile.gender_probability,
                "sample_size": new_profile.sample_size,
                "age": new_profile.age,
                "age_group": new_profile.age_group,
                "country_id": new_profile.country_id,
                "country_probability": new_profile.country_probability,
                "created_at": new_profile.created_at.isoformat().replace("+00:00", "Z"),
            },
        }

    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={"status": "error", "message": "External API timeout"},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Internal server error: {str(e)}"},
        )


#export profiles as CSV
@router.get("/export")
@limiter.limit("60/minute")
async def export_profiles(
    request: Request,
    format: str = Query("csv"),
    gender: Optional[str] = Query(None),
    age_group: Optional[str] = Query(None),
    country_id: Optional[str] = Query(None),
    min_age: Optional[int] = Query(None),
    max_age: Optional[int] = Query(None),
    sort_by: Optional[str] = Query("created_at"),
    order: Optional[str] = Query("desc"),
    api_version: bool = Depends(verify_api_version),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export profiles as CSV"""
    
    if format != "csv":
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": "Only CSV format is supported"}
        )
    
    query = db.query(Profile)
    
    # Apply filters
    if gender:
        query = query.filter(Profile.gender == gender.lower())
    if age_group:
        query = query.filter(Profile.age_group == age_group.lower())
    if country_id:
        query = query.filter(Profile.country_id == country_id.upper())
    if min_age is not None:
        query = query.filter(Profile.age >= min_age)
    if max_age is not None:
        query = query.filter(Profile.age <= max_age)
    
    # Apply sorting
    if sort_by == "age":
        order_func = desc if order == "desc" else asc
        query = query.order_by(order_func(Profile.age))
    else:
        order_func = desc if order == "desc" else asc
        query = query.order_by(order_func(Profile.created_at))
    
    profiles = query.all()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers in specified order
    headers = ["id", "name", "gender", "gender_probability", "age", "age_group", 
               "country_id", "country_name", "country_probability", "created_at"]
    writer.writerow(headers)
    
    # Write data
    for p in profiles:
        writer.writerow([
            p.id, p.name, p.gender, p.gender_probability, p.age, p.age_group,
            p.country_id, p.country_name, p.country_probability,
            p.created_at.isoformat().replace('+00:00', 'Z') if p.created_at else ""
        ])
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"profiles_{timestamp}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# list profiles with filtering, sorting, pagination
@router.get("", status_code=200)
@limiter.limit("60/minute")
async def list_profiles(
    request: Request,
    gender: Optional[str] = None,
    country_id: Optional[str] = None,
    age_group: Optional[str] = None,
    min_age: Optional[int] = Query(None, ge=0, le=150),
    max_age: Optional[int] = Query(None, ge=0, le=150),
    min_gender_probability: Optional[float] = Query(None, ge=0, le=1),
    min_country_probability: Optional[float] = Query(None, ge=0, le=1),
    sort_by: Optional[str] = Query(
        "created_at", pattern="^(age|created_at|gender_probability)$"
    ),
    order: Optional[str] = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    api_version: bool = Depends(verify_api_version),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # validate query parameters
    is_valide, error_message = validate_query_parameters(
        gender=gender,
        age_group=age_group,
        country_id=country_id,
        min_age=min_age,
        max_age=max_age,
        min_gender_probability=min_gender_probability,
        min_country_probability=min_country_probability,
        sort_by=sort_by,
        order=order,
    )

    if not is_valide:
        return JSONResponse(
            status_code=422, content={"status": "error", "message": error_message}
        )

    query = db.query(Profile)

    if gender:
        query = query.filter(func.lower(Profile.gender) == gender.lower())
    if country_id:
        query = query.filter(func.lower(Profile.country_id) == country_id.lower())
    if age_group:
        query = query.filter(func.lower(Profile.age_group) == age_group.lower())
    if min_age is not None:
        query = query.filter(Profile.age >= min_age)
    if max_age is not None:
        query = query.filter(Profile.age <= max_age)
    if min_gender_probability is not None:
        query = query.filter(Profile.gender_probability >= min_gender_probability)
    if min_country_probability is not None:
        query = query.filter(Profile.country_probability >= min_country_probability)

    profiles = query.order_by(Profile.created_at.desc()).all()

    total = query.count()

    # Apply sorting
    if sort_by == "age":
        order_func = desc if order == "desc" else asc
        query = query.order_by(order_func(Profile.age))
    elif sort_by == "gender_probability":
        order_func = desc if order == "desc" else asc
        query = query.order_by(order_func(Profile.gender_probability))
    else:
        order_func = desc if order == "desc" else asc
        query = query.order_by(order_func(Profile.created_at))

    offset = (page - 1) * limit
    profiles = query.limit(limit).offset(offset).all()
    total_pages = (total + limit - 1) // limit if total > 0 else 1

    # build links
    base_url = str(request.base_url).rstrip("/")
    links = {"self": f"{base_url}/api/profiles?page={page}&limit={limit}"}

    # links = {
    #     "self": f"{base_url}/api/profiles?page={page}&limit={limit}",
    #     "next": (
    #         f"{base_url}/api/profiles?page={page+1}&limit={limit}"
    #         if page < total_pages
    #         else None
    #     ),
    #     "prev": (
    #         f"{base_url}/api/profiles?page={page-1}&limit={limit}" if page > 1 else None
    #     ),
    # }
    if page < total_pages:
        links["next"] = f"{base_url}/api/profiles?page={page+1}&limit={limit}"
    if page > 1:
        links["prev"] = f"{base_url}/api/profiles?page={page-1}&limit={limit}"
    return {
        "status": "success",
        "count": len(profiles),
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages,
        "links": links,
        "data": [
            {
                "id": profile.id,
                "name": profile.name,
                "gender": profile.gender,
                "gender_probability": profile.gender_probability,
                "age": profile.age,
                "age_group": profile.age_group,
                "country_id": profile.country_id,
                "country_name": profile.country_name,
                "country_probability": profile.country_probability,
                "created_at": profile.created_at.isoformat().replace("+00:00", "Z"),
            }
            for profile in profiles
        ],
    }

# get profile statistics
@router.get("/demographics")
@limiter.limit("60/minute")
def get_demographics(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get demographic statistics"""
    total = db.query(Profile).count()

    gender_stats = (
        db.query(Profile.gender, func.count(Profile.id)).group_by(Profile.gender).all()
    )

    age_group_stats = (
        db.query(Profile.age_group, func.count(Profile.id))
        .group_by(Profile.age_group)
        .all()
    )

    country_stats = (
        db.query(Profile.country_id, func.count(Profile.id))
        .group_by(Profile.country_id)
        .order_by(func.count(Profile.id).desc())
        .limit(10)
        .all()
    )

    return {
        "status": "success",
        "total_profiles": total,
        "gender_distribution": {g: c for g, c in gender_stats},
        "age_group_distribution": {ag: c for ag, c in age_group_stats},
        "top_countries": [{"country_id": c, "count": cnt} for c, cnt in country_stats],
    }

#search profiles with natural language query
@router.get("/search")
@limiter.limit("60/minute")
def natural_search(
    request: Request,
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Natural language search endpoint"""

    # Parse natural language query
    parser = NaturalLanguageParser()
    filters = parser.parse(q)

    if not filters:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Unable to interpret query"},
        )

    # Build query
    query = db.query(Profile)

    # Apply filters
    if "gender" in filters:
        query = query.filter(Profile.gender == filters["gender"])
    if "age_group" in filters:
        query = query.filter(Profile.age_group == filters["age_group"])
    if "country_id" in filters:
        query = query.filter(Profile.country_id == filters["country_id"])
    if "min_age" in filters:
        query = query.filter(Profile.age >= filters["min_age"])
    if "max_age" in filters:
        query = query.filter(Profile.age <= filters["max_age"])

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * limit
    profiles = query.limit(limit).offset(offset).all()

    return {
        "status": "success",
        "page": page,
        "limit": limit,
        "total": total,
        "query_interpreted": filters,
        "data": [
            {
                "id": p.id,
                "name": p.name,
                "gender": p.gender,
                "gender_probability": p.gender_probability,
                "age": p.age,
                "age_group": p.age_group,
                "country_id": p.country_id,
                "country_name": p.country_name,
                "country_probability": p.country_probability,
                "created_at": p.created_at.isoformat().replace("+00:00", "Z"),
            }
            for p in profiles
        ],
    }

# get profile by id
@router.get("/{profile_id}", status_code=200)
@limiter.limit("60/minute")
def get_profile(
    request: Request,
    profile_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(Profile.id == profile_id).first()

    if not profile:
        return JSONResponse(
            status_code=404, content={"status": "error", "message": "profile not found"}
        )
    return {
        "status": "success",
        "data": {
            "id": profile.id,
            "name": profile.name,
            "gender": profile.gender,
            "gender_probability": profile.gender_probability,
            "age": profile.age,
            "age_group": profile.age_group,
            "country_id": profile.country_id,
            "country_name": profile.country_name,
            "country_probability": profile.country_probability,
            "created_at": profile.created_at.isoformat().replace("+00:00", "Z"),
        },
    }


#delete profile by id
@router.delete("/{profile_id}", status_code=204)
@limiter.limit("60/minute")
def delete_profile(
    request: Request,
    profile_id: str,
    api_version: bool = Depends(verify_api_version),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(Profile.id == profile_id).first()

    if not profile:
        return JSONResponse(
            status_code=404, content={"status": "error", "message": "Profile not found"}
        )
    db.delete(profile)
    db.commit()
    return
