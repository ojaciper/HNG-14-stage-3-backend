import httpx

def determin_age_group(age:int)-> str:
    if age <= 12:
        return "child"
    elif age <= 19:
        return "teenager"
    elif age <= 59:
        return "adult"
    else:
        return "senior"

async def call_genderize(name:str)-> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.genderize.io", params={"name":name})
        response.raise_for_status()
        data = response.json()
        if data.get('gender') is None or data.get("count") ==0:
            raise ValueError("Genederize returned invalid response")
        return {
            "gender":data['gender'],
            "gender_probability":data["probability"],
            "sample_size":data['count']
        }
     
async def call_agify(name:str)-> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get("https://api.agify.io", params={"name":name})
        response.raise_for_status()
        data =response.json()
        if data.get('age') is None:
            raise ValueError("Agify returned invalide response")
        age = data['age']
     
        return {
            "age":age,
            "age_group":determin_age_group(age)
        }
        
async def call_nationalize(name:str)-> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get("https://api.nationalize.io", params={"name":name})
        response.raise_for_status()
        data = response.json()
        
        if not data.get("country") or len(data['country'])==0:
            raise ValueError("Nationalize returned invalide response")
        
        top_country = max(data["country"],key=lambda x:x['probability'])
        return{
            "country_id":top_country["country_id"],
            "country_probability":top_country['probability']
        }