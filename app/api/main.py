from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, Depends, Query
from fastapi.responses import JSONResponse
import httpx
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from app.helper.helper import determin_age_group
from app.schama.profile import ProfileCreate
from app.database.database import get_db, engine, Base
from app.database.model import Profile, generate_uuid7
from app.utils.natural_lang import NaturalLanguageParser
from app.helper.validate_query import validate_query_parameters


Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.post("/api/profiles", status_code=201)
async def create_profile(profile: ProfileCreate, db: Session = Depends(get_db)):

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


@app.get("/api/profiles", status_code=200)
def list_profiles(
    gender: Optional[str] = None,
    country_id: Optional[str] = None,
    age_group: Optional[str] = None,
    min_age: Optional[int] = Query(None, ge=0, le=150),
    max_age: Optional[int] = Query(None, ge=0, le=150),
    min_gender_probability: Optional[float] = Query(None, ge=0, le=1),
    min_country_probability: Optional[float] = Query(None, ge=0, le=1),
    sort_by: Optional[str] = Query(
        "created_at", regex="^(age|created_at|gender_probability)$"
    ),
    order: Optional[str] = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    #validate query parameters
    is_valide,error_message =validate_query_parameters(
        gender=gender,
        age_group=age_group,
        country_id=country_id,
        min_age=min_age,
        max_age=max_age,
        min_gender_probability=min_gender_probability,
        min_country_probability=min_country_probability,
        sort_by=sort_by,
        order=order
    )
    
    if not is_valide:
        return JSONResponse(
            status_code=422,
            content={"status": "error", "message": error_message}
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
    return {
        "status": "success",
        "count": len(profiles),
        "page": page,
        "limit": limit,
        "total": total,
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
    
    

@app.get("/api/profiles/search")
def natural_search(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Natural language search endpoint"""
    
    # Parse natural language query
    parser = NaturalLanguageParser()
    filters = parser.parse(q)
    
    if not filters:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Unable to interpret query"}
        )
    
    # Build query
    query = db.query(Profile)
    
    # Apply filters
    if 'gender' in filters:
        query = query.filter(Profile.gender == filters['gender'])
    if 'age_group' in filters:
        query = query.filter(Profile.age_group == filters['age_group'])
    if 'country_id' in filters:
        query = query.filter(Profile.country_id == filters['country_id'])
    if 'min_age' in filters:
        query = query.filter(Profile.age >= filters['min_age'])
    if 'max_age' in filters:
        query = query.filter(Profile.age <= filters['max_age'])
    
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
                "created_at": p.created_at.isoformat().replace('+00:00', 'Z')
            }
            for p in profiles
        ]
    }



@app.get("/api/profiles/{profile_id}", status_code=200)
def get_profile(profile_id: str, db: Session = Depends(get_db)):
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




@app.get("/api/profiles/stats/demographics")
def get_demographics(db: Session = Depends(get_db)):
    """Get demographic statistics"""
    total = db.query(Profile).count()
    
    gender_stats = db.query(
        Profile.gender, func.count(Profile.id)
    ).group_by(Profile.gender).all()
    
    age_group_stats = db.query(
        Profile.age_group, func.count(Profile.id)
    ).group_by(Profile.age_group).all()
    
    country_stats = db.query(
        Profile.country_id, func.count(Profile.id)
    ).group_by(Profile.country_id).order_by(func.count(Profile.id).desc()).limit(10).all()
    
    return {
        "status": "success",
        "total_profiles": total,
        "gender_distribution": {g: c for g, c in gender_stats},
        "age_group_distribution": {ag: c for ag, c in age_group_stats},
        "top_countries": [{"country_id": c, "count": cnt} for c, cnt in country_stats]
    }



@app.delete("/api/profiles/{profile_id}", status_code=204)
def delete_profile(profile_id: str, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.id == profile_id).first()

    if not profile:
        return JSONResponse(
            status_code=404, content={"status": "error", "message": "Profile not found"}
        )
    db.delete(profile)
    db.commit()

    return


@app.get("/")
def root():
    return {"message": "Name Profiler API", "version": "1.0.0"}
