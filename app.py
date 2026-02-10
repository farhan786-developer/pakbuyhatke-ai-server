# app.py - Pak Buy Pro AI Server
# Production-ready with Gemini API pre-configured

from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
import re
import os
from functools import lru_cache
import time
import signal

app = Flask(__name__)
CORS(app)

# Gemini API Configuration (Pre-configured for production)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyCS_iFTMJ7MqpWhKhvrUlhO_SLcJsL-_L4')
AI_ENABLED = False

try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
    # Test connection
    model.generate_content("test")
    AI_ENABLED = True
    print("✅ Gemini AI: Connected successfully")
except Exception as e:
    print(f"⚠️ Gemini AI initialization failed: {e}")
    print("🔧 Fallback to regex mode enabled")

# Cache for performance (1000 products)
@lru_cache(maxsize=1000)
def cached_clean_title(title):
    """Cache cleaned titles for speed"""
    return clean_title_with_ai(title)

def timeout_handler(signum, frame):
    """Handle AI timeout"""
    raise TimeoutError("AI processing timeout")

def clean_title_with_ai(title):
    """
    Use Gemini AI to extract clean product keywords
    Timeout: 3 seconds
    """
    if not AI_ENABLED:
        return None
        
    try:
        # Set timeout alarm (Unix systems only)
        if hasattr(signal, 'SIGALRM'):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(3)  # 3 second timeout
        
        prompt = f"""Extract only the essential product information from this title.

Remove: promotional text, warranty info, shipping info, seller info, PTA approved, official warranty, cash on delivery, installment, sealed, original, authentic, new, limited stock, sale, discount, special offer, hot deal.

Keep: brand, model, RAM, storage, screen size, processor, color (only if important).

Title: {title}

Return ONLY the cleaned product name with key specs in this exact format:
Brand Model RAM Storage

Examples:
- Input: "Samsung Galaxy A15 8GB/256GB PTA Approved Official Warranty Fast Shipping"
  Output: "Samsung Galaxy A15 8GB 256GB"
  
- Input: "iPhone 13 Pro Max 256GB Factory Unlocked Original Apple Warranty"
  Output: "iPhone 13 Pro Max 256GB"
  
- Input: "HP Pavilion Gaming Laptop i5 11th Gen 8GB RAM 512GB SSD"
  Output: "HP Pavilion Gaming i5 11th Gen 8GB 512GB"

Now clean this title (reply with ONLY the cleaned version, no explanation):"""

        response = model.generate_content(prompt)
        cleaned = response.text.strip()
        
        # Cancel alarm
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)
        
        # Remove any quotes or extra formatting
        cleaned = cleaned.replace('"', '').replace("'", "").strip()
        
        print(f"✅ AI Cleaned: '{title[:50]}...' → '{cleaned}'")
        return cleaned
        
    except TimeoutError:
        print("⏱️ AI timeout (3s exceeded)")
        return None
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return None

def clean_title_with_regex(title):
    """
    Fallback: Advanced regex-based cleaning
    Handles Pakistani e-commerce titles
    """
    # Remove common garbage patterns
    garbage_patterns = [
        r'PTA\s*Approved?',
        r'Official\s*Warranty',
        r'Fast\s*Shipping',
        r'Cash\s*on\s*Delivery',
        r'Free\s*Delivery',
        r'Installments?',
        r'Easy\s*Payment',
        r'Original',
        r'Authentic',
        r'\bNew\b',
        r'\bSealed\b',
        r'In\s*Stock',
        r'Available',
        r'Limited\s*Stock',
        r'Hot\s*Deal',
        r'Sale',
        r'Discount',
        r'\d+%\s*Off',
        r'Special\s*Offer',
        r'₹|Rs\.?|PKR',
        r'[⭐★✓✔]+',
        r'\|',
        r'•'
    ]
    
    cleaned = title
    for pattern in garbage_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Clean up whitespace and symbols
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = re.sub(r'[|•\-_]+', ' ', cleaned)
    cleaned = re.sub(r'\([^)]*\)', '', cleaned)  # Remove parentheses content
    cleaned = cleaned.strip()
    
    # Extract key components using patterns
    
    # Mobile phone pattern (Samsung, iPhone, Xiaomi, etc.)
    mobile_brands = ['Samsung', 'iPhone', 'Xiaomi', 'Oppo', 'Vivo', 'Realme', 
                     'Infinix', 'Tecno', 'OnePlus', 'Google', 'Nokia', 'Huawei', 'Motorola']
    
    for brand in mobile_brands:
        pattern = f'({brand})\s+([A-Z0-9][A-Za-z0-9\\s]+?)(?:\s+(\d+GB))?(?:\s+(\d+GB))?'
        match = re.search(pattern, cleaned, re.IGNORECASE)
        
        if match:
            brand_name = match.group(1)
            model = match.group(2).strip()
            ram = match.group(3) or ''
            storage = match.group(4) or ''
            
            # Clean up model name (remove trailing junk)
            model = re.sub(r'\s+(with|and|for|official|factory).*$', '', model, flags=re.IGNORECASE)
            
            cleaned = f"{brand_name} {model} {ram} {storage}".strip()
            break
    
    # Laptop pattern
    laptop_brands = ['HP', 'Dell', 'Lenovo', 'Asus', 'Acer', 'MSI', 'Apple', 'MacBook']
    
    for brand in laptop_brands:
        pattern = f'({brand})\s+([A-Za-z0-9\\s]+?)(?:\s+(i[3579]|Ryzen\s*[3579]|M[12]))?'
        match = re.search(pattern, cleaned, re.IGNORECASE)
        
        if match:
            brand_name = match.group(1)
            model = match.group(2).strip()
            processor = match.group(3) or ''
            
            # Extract RAM and storage if present
            ram_match = re.search(r'(\d+GB)\s*RAM', cleaned, re.IGNORECASE)
            storage_match = re.search(r'(\d+GB|\d+TB)\s*(?:SSD|HDD|Storage)', cleaned, re.IGNORECASE)
            
            ram = ram_match.group(1) if ram_match else ''
            storage = storage_match.group(1) if storage_match else ''
            
            cleaned = f"{brand_name} {model} {processor} {ram} {storage}".strip()
            break
    
    # Final cleanup
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    print(f"🔧 Regex Cleaned: '{title[:50]}...' → '{cleaned}'")
    return cleaned

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/clean-title', methods=['POST'])
def clean_title_endpoint():
    """
    Main endpoint: Clean product title
    Hybrid: AI first, regex fallback
    """
    try:
        data = request.json
        title = data.get('title', '')
        timeout = data.get('timeout', 3)
        
        if not title:
            return jsonify({
                'success': False,
                'error': 'No title provided'
            }), 400
        
        print(f"\n📥 Clean request: {title[:60]}...")
        
        start_time = time.time()
        
        # PLAN A: Try AI (with caching)
        ai_result = None
        if AI_ENABLED:
            try:
                ai_result = cached_clean_title(title)
                elapsed = time.time() - start_time
                
                if elapsed > timeout:
                    print(f"⚠️ AI too slow ({elapsed:.2f}s)")
                    ai_result = None
            except Exception as e:
                print(f"⚠️ AI failed: {e}")
                ai_result = None
        
        # PLAN B: Regex fallback
        if not ai_result:
            regex_result = clean_title_with_regex(title)
            return jsonify({
                'success': True,
                'original': title,
                'cleaned': regex_result,
                'method': 'regex',
                'confidence': 0.75,
                'time_ms': int((time.time() - start_time) * 1000)
            })
        
        # AI succeeded
        return jsonify({
            'success': True,
            'original': title,
            'cleaned': ai_result,
            'method': 'ai',
            'confidence': 0.95,
            'time_ms': int((time.time() - start_time) * 1000)
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        # Ultimate fallback
        return jsonify({
            'success': True,
            'original': title,
            'cleaned': title,
            'method': 'none',
            'confidence': 0.5,
            'error': str(e)
        })

@app.route('/clean-batch', methods=['POST'])
def clean_batch_endpoint():
    """Clean multiple titles at once"""
    try:
        data = request.json
        titles = data.get('titles', [])
        
        results = []
        for title in titles:
            try:
                cleaned = cached_clean_title(title) if AI_ENABLED else None
                if not cleaned:
                    cleaned = clean_title_with_regex(title)
            except:
                cleaned = clean_title_with_regex(title)
            
            results.append({
                'original': title,
                'cleaned': cleaned
            })
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    cache_info = cached_clean_title.cache_info()
    
    return jsonify({
        'status': 'ok',
        'service': 'Pak Buy Pro AI Server',
        'ai_available': AI_ENABLED,
        'cache_size': cache_info.currsize,
        'cache_hits': cache_info.hits,
        'cache_misses': cache_info.misses,
        'uptime': 'running'
    })

@app.route('/test', methods=['GET'])
def test_endpoint():
    """Test with sample Pakistani e-commerce titles"""
    test_titles = [
        "Samsung Galaxy A15 8GB/256GB PTA Approved Official Warranty Fast Shipping",
        "iPhone 13 Pro Max 256GB Factory Unlocked Original Apple Warranty Cash on Delivery",
        "HP Pavilion Gaming Laptop i5 11th Gen 8GB RAM 512GB SSD Official Warranty",
        "Xiaomi Redmi Note 12 Pro 5G 8GB+256GB Global Version PTA Approved"
    ]
    
    results = []
    for title in test_titles:
        try:
            ai_cleaned = clean_title_with_ai(title) if AI_ENABLED else "AI not available"
        except:
            ai_cleaned = "AI failed"
        
        regex_cleaned = clean_title_with_regex(title)
        
        results.append({
            'original': title,
            'ai_cleaned': ai_cleaned,
            'regex_cleaned': regex_cleaned
        })
    
    return jsonify({
        'test_results': results,
        'ai_enabled': AI_ENABLED
    })

@app.route('/', methods=['GET'])
def index():
    """Welcome page"""
    return jsonify({
        'service': 'Pak Buy Pro AI Server',
        'version': '1.0.0',
        'status': 'running',
        'ai_status': 'enabled' if AI_ENABLED else 'disabled (fallback active)',
        'endpoints': {
            '/health': 'Health check',
            '/clean-title': 'Clean single title (POST)',
            '/clean-batch': 'Clean multiple titles (POST)',
            '/test': 'Test with sample data'
        }
    })

# ============================================
# START SERVER
# ============================================

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    
    print("\n" + "="*50)
    print("🚀 Pak Buy Pro AI Server Starting...")
    print("="*50)
    print(f"🤖 Gemini AI: {'✅ Available' if AI_ENABLED else '❌ Using fallback mode'}")
    print("🔧 Regex Fallback: ✅ Always available")
    print("⚡ Hybrid Mode: ACTIVATED")
    print("💾 Cache: 1000 products")
    print(f"📍 Port: {port}")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)
