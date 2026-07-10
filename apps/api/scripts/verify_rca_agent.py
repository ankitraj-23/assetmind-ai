import sys

import httpx

API_URL = "http://localhost:8000/agents/rca"


def verify_rca_agent():
    """
    Calls the /agents/rca endpoint and verifies the response structure.
    """
    print("--- Verifying RCA Agent ---")
    payload = {"asset_tag": "P-101", "symptom": "high vibration after seal replacement"}

    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(API_URL, json=payload)

            if response.status_code != 200:
                print(f"FAIL: Expected status code 200, but got {response.status_code}")
                print("Response body:", response.text)
                sys.exit(1)

            print(f"OK: Received status code {response.status_code}")
            data = response.json()

            # 1. Check top-level keys
            expected_keys = {
                "asset_tag",
                "symptom",
                "summary",
                "likely_causes",
                "recommended_actions",
                "missing_information",
            }
            actual_keys = set(data.keys())
            if not expected_keys.issubset(actual_keys):
                print(f"FAIL: Response missing required keys. Expected: {expected_keys}, Got: {actual_keys}")
                sys.exit(1)
            print("OK: All top-level keys are present.")

            # 2. Check asset_tag and symptom
            assert data["asset_tag"] == payload["asset_tag"], "FAIL: asset_tag mismatch"
            assert data["symptom"] == payload["symptom"], "FAIL: symptom mismatch"
            print("OK: asset_tag and symptom match request.")

            # 3. Check likely_causes (at least 2 as per requirement)
            causes = data.get("likely_causes", [])
            if not isinstance(causes, list) or len(causes) < 2:
                print(f"FAIL: Expected at least 2 likely_causes, but found {len(causes)}.")
                sys.exit(1)
            print(f"OK: Found {len(causes)} likely causes (>= 2).")

            # 4. Check structure of the first cause and its evidence
            first_cause = causes[0]
            assert "cause" in first_cause and first_cause["cause"], "FAIL: first cause missing 'cause'."
            assert "confidence" in first_cause, "FAIL: first cause missing 'confidence'."
            assert "evidence" in first_cause and first_cause["evidence"], "FAIL: first cause missing 'evidence'."
            first_evidence = first_cause["evidence"][0]
            assert "source" in first_evidence and first_evidence["source"], "FAIL: first evidence missing 'source'."
            assert "text" in first_evidence and first_evidence["text"], "FAIL: first evidence missing 'text'."
            print("OK: First cause and evidence have correct structure.")

            # 5. Check recommended_actions and missing_information are not empty
            assert data.get("recommended_actions"), "FAIL: recommended_actions is missing or empty."
            print("OK: recommended_actions is present and not empty.")
            assert data.get("missing_information"), "FAIL: missing_information is missing or empty."
            print("OK: missing_information is present and not empty.")

            print("\n--- RCA Agent Verification PASSED ---")

    except httpx.RequestError as e:
        print(f"FAIL: HTTP request failed: {e}\nIs the backend server running on http://localhost:8000?")
        sys.exit(1)
    except Exception as e:
        print(f"FAIL: An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    verify_rca_agent()