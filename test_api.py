import httpx
import json

# Test API endpoints
base_url = "http://localhost:8000/api/v1"

def test_api():
    try:
        with httpx.Client(timeout=5.0) as client:
            # Test health endpoint
            response = client.get(f"{base_url}/health")
            print("Health endpoint:", response.status_code, response.json())
            
            # Test creating a counselor
            counselor_data = {
                "name": "Coach Miller",
                "specialization": "Baseball Coach",
                "therapeutic_style": "Tough love with encouragement",
                "credentials": "20 years coaching experience",
                "session_template": "Alright team, let's talk about what's on your mind today."
            }
            
            response = client.post(f"{base_url}/counselors", json=counselor_data)
            print("Create counselor:", response.status_code, response.json())
            
            # Get all counselors
            response = client.get(f"{base_url}/counselors")
            print("Get counselors:", response.status_code, response.json())
            
    except Exception as e:
        print(f"Error testing API: {e}")

if __name__ == "__main__":
    test_api()