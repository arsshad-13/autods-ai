import httpx
import uuid
import sys

def test_auth():
    print("Testing Auth Endpoints via HTTP...")
    email = f"test_{uuid.uuid4()}@example.com"
    password = "superlongpasswordthatisdefinitelymorethan72characterslongtocausebcrypttofailifnotprehashedcorrectly_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    
    # 1. Register
    response = httpx.post("http://localhost:8001/api/v1/auth/register", json={
        "name": "Test User",
        "email": email,
        "password": password
    })
    print("Register Response:", response.status_code, response.text)
    if response.status_code != 201:
        sys.exit(1)

    # 2. Login
    response = httpx.post("http://localhost:8001/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    print("Login Response:", response.status_code, response.text)
    if response.status_code != 200:
        sys.exit(1)
        
    access_token = response.json()["access_token"]
    
    # 3. Get Me
    response = httpx.get("http://localhost:8001/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    print("Me Response:", response.status_code, response.text)
    if response.status_code != 200:
        sys.exit(1)

if __name__ == "__main__":
    test_auth()
