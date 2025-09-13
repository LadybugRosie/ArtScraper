from flask import Flask, request, render_template, jsonify
import requests
import os
from PIL import Image
import tempfile
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

SERPAPI_KEY = os.getenv('SERPAPI_KEY')  # Get free key from serpapi.com

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check-plagiarism', methods=['POST'])
def check_plagiarism():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save temporarily
    temp_path = os.path.join('uploads', file.filename)
    file.save(temp_path)
    
    # Get image info
    try:
        img = Image.open(temp_path)
        img_info = {
            'size': img.size,
            'format': img.format,
            'filename': file.filename
        }
    except Exception as e:
        return jsonify({'error': 'Invalid image file'}), 400
    
    # Search for similar images
    results = search_similar_images(temp_path)
    
    # Clean up
    os.remove(temp_path)
    
    return jsonify({
        'image_info': img_info,
        'results': results
    })

def search_similar_images(image_path):
    """Use SerpApi to search for similar images"""
    
    if not SERPAPI_KEY:
        # Fallback: return mock results for demo
        return {
            'matches': [
                {
                    'title': 'Demo Result - Setup SerpApi key for real results',
                    'source': 'example.com',
                    'thumbnail': 'https://via.placeholder.com/150',
                    'similarity': 'Unknown'
                }
            ],
            'total_found': 1
        }
    
    try:
        # Upload image to get search URL (simplified)
        # In real implementation, you'd need to handle image upload properly
        
        params = {
            'engine': 'google_reverse_image',
            'image_file': open(image_path, 'rb'),
            'api_key': SERPAPI_KEY
        }
        
        response = requests.post('https://serpapi.com/search', files=params)
        data = response.json()
        
        matches = []
        if 'image_results' in data:
            for result in data['image_results'][:5]:  # Top 5 results
                matches.append({
                    'title': result.get('title', 'No title'),
                    'source': result.get('source', 'Unknown source'),
                    'thumbnail': result.get('thumbnail', ''),
                    'link': result.get('link', ''),
                    'similarity': 'High'  # SerpApi doesn't provide similarity scores
                })
        
        return {
            'matches': matches,
            'total_found': len(matches)
        }
        
    except Exception as e:
        return {
            'matches': [],
            'total_found': 0,
            'error': str(e)
        }

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    app.run(debug=True)
