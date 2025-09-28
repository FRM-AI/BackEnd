#!/usr/bin/env python3
"""
Test script for streaming insights functionality
"""
import requests
import json
import time

def test_streaming_insights():
    """Test the streaming insights endpoint"""
    
    url = "http://localhost:8000/api/insights/stream"
    
    payload = {
        "ticker": "VCB",
        "asset_type": "stock",
        "look_back_days": 7,  # Short for faster testing
        "start_date": "2024-01-01",
        "end_date": "2024-12-31"
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }
    
    print(f"🧪 Testing streaming insights for {payload['ticker']}...")
    print(f"📡 Connecting to: {url}")
    print(f"📦 Payload: {json.dumps(payload, indent=2)}")
    print("-" * 50)
    
    try:
        response = requests.post(url, 
                               json=payload, 
                               headers=headers, 
                               stream=True,
                               timeout=120)
        
        if response.status_code == 200:
            print("✅ Connection successful! Streaming data:")
            print("-" * 50)
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        try:
                            data = json.loads(line_str[6:])  # Remove 'data: ' prefix
                            
                            # Format output based on data type
                            if data['type'] == 'metadata':
                                print(f"📋 METADATA: {json.dumps(data['data'], indent=2)}")
                            elif data['type'] == 'status':
                                print(f"⏳ STATUS: {data['message']} ({data.get('progress', 0)}%)")
                            elif data['type'] == 'section_start':
                                print(f"🚀 SECTION START: {data['title']}")
                            elif data['type'] == 'content':
                                print(f"📝 CONTENT [{data['section']}]: {data['text'][:100]}...")
                            elif data['type'] == 'section_end':
                                print(f"✅ SECTION END: {data['section']}")
                            elif data['type'] == 'complete':
                                print(f"🎉 COMPLETE: {data['message']}")
                                break
                            elif data['type'] == 'error':
                                print(f"❌ ERROR: {data['message']}")
                                break
                            else:
                                print(f"📡 DATA: {json.dumps(data)}")
                                
                        except json.JSONDecodeError as e:
                            print(f"⚠️  JSON Parse Error: {e} for line: {line_str}")
                        except Exception as e:
                            print(f"⚠️  Processing Error: {e}")
                            
        else:
            print(f"❌ Connection failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def test_legacy_insights():
    """Test the legacy insights endpoint for comparison"""
    
    url = "http://localhost:8000/api/insights"
    
    payload = {
        "ticker": "VCB",
        "asset_type": "stock", 
        "look_back_days": 7
    }
    
    print(f"\n🔄 Testing legacy insights for comparison...")
    print("-" * 50)
    
    start_time = time.time()
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Legacy request completed in {elapsed:.2f}s")
            print(f"📊 Technical Analysis Length: {len(data.get('technical_analysis', ''))}")
            print(f"📰 News Analysis Length: {len(data.get('news_analysis', ''))}")  
            print(f"🎯 Combined Analysis Length: {len(data.get('combined_analysis', ''))}")
        else:
            print(f"❌ Legacy request failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Legacy request error: {e}")

if __name__ == "__main__":
    print("🚀 Starting Streaming Insights Test")
    print("=" * 60)
    
    # Test streaming first
    test_streaming_insights()
    
    # Test legacy for comparison  
    test_legacy_insights()
    
    print("\n" + "=" * 60)
    print("✨ Test completed!")