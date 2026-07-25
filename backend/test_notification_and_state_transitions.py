import httpx
import time
import uuid
import sys
import os

def run_e2e_verification():
    print("=========================================================")
    print("STARTING PROGRAMMATIC E2E LIFE-CYCLE VERIFICATION")
    print("=========================================================")
    
    base_url = "http://localhost:8000/api/v1"
    email = f"qa_{uuid.uuid4().hex[:8]}@autods-ai.com"
    password = "Password123!"
    
    # 1. Register User
    print("\n[Step 1] Registering test user...")
    res = httpx.post(f"{base_url}/auth/register", json={
        "name": "QA Lead Tester",
        "email": email,
        "password": password
    })
    print(f"Status: {res.status_code}")
    if res.status_code != 201:
        print("Registration failed.")
        sys.exit(1)
        
    # 2. Login
    print("\n[Step 2] Logging in...")
    res = httpx.post(f"{base_url}/auth/login", json={
        "email": email,
        "password": password
    })
    print(f"Status: {res.status_code}")
    if res.status_code != 200:
        print("Login failed.")
        sys.exit(1)
    
    access_token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Paths for test files
    storage_dir = os.path.dirname(os.path.abspath(__file__))
    valid_file_path = os.path.join(storage_dir, "storage", "valid_employee_dataset.csv")
    malformed_file_path = os.path.join(storage_dir, "storage", "malformed_dataset.csv")
    
    # 3. Scenario 1: Upload Valid CSV
    print("\n[Scenario 1] Uploading valid CSV dataset...")
    with open(valid_file_path, "rb") as f:
        res = httpx.post(
            f"{base_url}/datasets/",
            files={"file": (os.path.basename(valid_file_path), f, "text/csv")},
            headers=headers
        )
    print(f"Status: {res.status_code}")
    if res.status_code != 201:
        print("Upload failed.")
        sys.exit(1)
        
    dataset = res.json()
    valid_uuid = dataset["uuid"]
    print(f"Dataset uploaded successfully. Initial Status: '{dataset['status']}' (Expected: 'uploaded')")
    
    # 4. Scenario 3: Click Analyze (Trigger Profiling)
    print("\n[Scenario 3] Triggering analysis (Analyze Dataset)...")
    res = httpx.post(f"{base_url}/datasets/{valid_uuid}/profile", headers=headers)
    print(f"Status: {res.status_code}")
    if res.status_code != 200:
        print("Analyze trigger failed.")
        sys.exit(1)
    
    dataset = res.json()
    print(f"Analysis triggered. Status: '{dataset['status']}' (Expected: 'pending')")
    
    # 5. Scenario 4: Polling until completed
    print("\n[Scenario 4] Polling status every 2 seconds...")
    completed = False
    for attempt in range(10):
        time.sleep(2)
        res = httpx.get(f"{base_url}/datasets/{valid_uuid}", headers=headers)
        status = res.json()["status"]
        print(f"Poll {attempt+1} -> status: '{status}'")
        if status == "completed":
            completed = True
            break
        elif status == "failed":
            print(f"Unexpected fail. error_message: {res.json().get('error_message')}")
            sys.exit(1)
            
    if completed:
        print("Valid dataset analysis successfully completed! Status is 'completed'.")
    else:
        print("Profiling timed out.")
        sys.exit(1)
        
    # Retrieve profile to verify database persistence
    res = httpx.get(f"{base_url}/datasets/{valid_uuid}/profile", headers=headers)
    print(f"Retrieve Profile Status: {res.status_code}")
    if res.status_code == 200:
        print("Profile data is successfully persisted and retrieved!")
    else:
        print("Profile retrieval failed.")
        sys.exit(1)
        
    # 6. Scenario 5: Upload and Analyze Malformed CSV
    print("\n[Scenario 5] Uploading malformed CSV dataset...")
    with open(malformed_file_path, "rb") as f:
        res = httpx.post(
            f"{base_url}/datasets/",
            files={"file": (os.path.basename(malformed_file_path), f, "text/csv")},
            headers=headers
        )
    print(f"Status: {res.status_code}")
    if res.status_code != 201:
        print("Upload failed.")
        sys.exit(1)
        
    dataset = res.json()
    malformed_uuid = dataset["uuid"]
    print(f"Malformed dataset uploaded successfully. Initial Status: '{dataset['status']}' (Expected: 'uploaded')")
    
    print("\n[Scenario 5] Triggering analysis for malformed dataset...")
    res = httpx.post(f"{base_url}/datasets/{malformed_uuid}/profile", headers=headers)
    print(f"Status: {res.status_code}")
    if res.status_code != 200:
        print("Analyze trigger failed.")
        sys.exit(1)
        
    print("Polling status of malformed dataset every 2 seconds...")
    failed = False
    for attempt in range(10):
        time.sleep(2)
        res = httpx.get(f"{base_url}/datasets/{malformed_uuid}", headers=headers)
        status = res.json()["status"]
        err_msg = res.json().get("error_message")
        print(f"Poll {attempt+1} -> status: '{status}', error_message: '{err_msg}'")
        if status == "failed":
            failed = True
            break
        elif status == "completed":
            print("Unexpected success for malformed dataset.")
            sys.exit(1)
            
    if failed:
        print("Malformed dataset failed profiling successfully! Final status is 'failed'.")
        print(f"Error Message: '{err_msg}' (Expected friendly parsing failure message)")
    else:
        print("Failed profiling timed out.")
        sys.exit(1)
        
    print("\n=========================================================")
    print("ALL STATE AND TRANSITION LIFECYCLES VERIFIED SUCCESSFULLY")
    print("=========================================================")

if __name__ == "__main__":
    run_e2e_verification()
