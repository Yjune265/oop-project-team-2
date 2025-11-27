import requests, os


API_KEY = os.getenv("FOOD_SAFETY_API_KEY", "test")




def search_supplement(keyword):
    url = f"https://api.foodsafety.go.kr/api/{API_KEY}/C003/json/1/10/PRDLST_NM={keyword}"
    try:
        response = requests.get(url)
        return response.json()
    except:
        return {"error": "API request failed"}