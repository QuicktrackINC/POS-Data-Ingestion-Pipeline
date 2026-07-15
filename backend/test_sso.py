import os
import sys
import jwt
from fastapi.testclient import TestClient

os.environ["SSO_SHARED_SECRET"] = "quicktrack-dev-secret-change-in-production"
sys.path.append(os.path.dirname(__file__))

from main import app

def run_tests():
    print("=== Testing SSO for pos-data-pipeline ===")
    with TestClient(app) as client:
        for role in ["SUPERADMIN", "ADMIN", "STAFF"]:
            print(f"\nTesting Role: {role}")
            payload = {"email": f"test-{role.lower()}@quicktrack.com", "role": role}
            token = jwt.encode(payload, "quicktrack-dev-secret-change-in-production", algorithm="HS256")
            
            resp = client.post("/api/auth/sso", json={"token": token})
            print("Status:", resp.status_code)
            if resp.status_code == 200:
                print("✅ Handshake Successful!")
            else:
                print("❌ Handshake Failed!")
                print(resp.text)

if __name__ == "__main__":
    run_tests()
