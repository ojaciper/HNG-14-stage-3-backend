from typing import Optional
import re
def validate_query_parameters(
    gender: Optional[str] = None,
    age_group: Optional[str] = None,
    country_id: Optional[str] = None,
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
    min_gender_probability: Optional[float] = None,
    min_country_probability: Optional[float] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None
):
    
    # Validate gender
    if gender is not None:
        if gender.lower() not in ['male', 'female']:
            return False, "Invalid gender. Must be 'male' or 'female'"
    
    # Validate age_group
    if age_group is not None:
        if age_group.lower() not in ['child', 'teenager', 'adult', 'senior']:
            return False, "Invalid age_group. Must be 'child', 'teenager', 'adult', or 'senior'"
    
    # Validate country_id (2-letter ISO code)
    if country_id is not None:
        if not re.match(r'^[A-Z]{2}$', country_id.upper()):
            return False, "Invalid country_id. Must be 2-letter ISO code (e.g., NG, US)"
    
    # Validate age range
    if min_age is not None and max_age is not None:
        if min_age > max_age:
            return False, "min_age cannot be greater than max_age"
    
    if min_age is not None and (min_age < 0 or min_age > 150):
        return False, "min_age must be between 0 and 150"
    
    if max_age is not None and (max_age < 0 or max_age > 150):
        return False, "max_age must be between 0 and 150"
    
    # Validate probability values
    if min_gender_probability is not None:
        if min_gender_probability < 0 or min_gender_probability > 1:
            return False, "min_gender_probability must be between 0 and 1"
    
    if min_country_probability is not None:
        if min_country_probability < 0 or min_country_probability > 1:
            return False, "min_country_probability must be between 0 and 1"
    
    # Validate sort_by
    if sort_by is not None:
        if sort_by not in ['age', 'created_at', 'gender_probability']:
            return False, "Invalid sort_by. Must be 'age', 'created_at', or 'gender_probability'"
    
    # Validate order
    if order is not None:
        if order not in ['asc', 'desc']:
            return False, "Invalid order. Must be 'asc' or 'desc'"
    
    return True, "Valid"