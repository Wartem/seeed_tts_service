import requests
import time
import sys

def check_service():
    """Check service health and status"""
    try:
        # Basic health check
        response = requests.get("http://localhost:8912/metrics", timeout=5)
        print("\nService metrics:")
        print(response.json())
        
        # Check queue status
        response = requests.get("http://localhost:8912/status", timeout=5)
        print("\nQueue status:")
        print(response.json())
        
        # Test small TTS request
        response = requests.post(
            "http://localhost:8912/tts",
            json={"text": "Test", "priority": True},
            timeout=5
        )
        print("\nTest TTS request result:")
        print(response.json())
        
    except requests.exceptions.Timeout:
        print("Service timeout - possible deadlock")
    except requests.exceptions.ConnectionError:
        print("Cannot connect to service")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_service()