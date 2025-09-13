from flask import Flask, request, render_template, jsonify
import requests
import os
from PIL import Image
import tempfile
import base64
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# API Keys
SERPAPI_KEY = os.getenv('SERPAPI_KEY')
TOOLHOUSE_API_KEY = os.getenv('TOOLHOUSE_API_KEY')  # Add this to your .env file
TOOLHOUSE_BASE_URL = "https://api.toolhouse.ai/v1"


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

    # Search for similar images using multiple methods
    serpapi_results = search_similar_images_serpapi(temp_path)
    toolhouse_results = search_similar_images_toolhouse(temp_path)

    # Combine results
    combined_results = combine_search_results(serpapi_results, toolhouse_results)

    # Clean up
    os.remove(temp_path)

    return jsonify({
        'image_info': img_info,
        'results': combined_results,
        'sources_used': ['SerpAPI', 'Toolhouse']
    })


def search_similar_images_serpapi(image_path):
    """Use SerpApi to search for similar images"""

    if not SERPAPI_KEY:
        return {'matches': [], 'total_found': 0, 'source': 'serpapi'}

    try:
        params = {
            'engine': 'google_reverse_image',
            'api_key': SERPAPI_KEY
        }

        files = {
            'image_file': open(image_path, 'rb')
        }

        response = requests.post('https://serpapi.com/search', data=params, files=files)
        data = response.json()

        matches = []
        if 'image_results' in data:
            for result in data['image_results'][:5]:
                matches.append({
                    'title': result.get('title', 'No title'),
                    'source': result.get('source', 'Unknown source'),
                    'thumbnail': result.get('thumbnail', ''),
                    'link': result.get('link', ''),
                    'similarity': 'High',
                    'search_engine': 'Google (SerpAPI)'
                })

        return {
            'matches': matches,
            'total_found': len(matches),
            'source': 'serpapi'
        }

    except Exception as e:
        return {
            'matches': [],
            'total_found': 0,
            'error': str(e),
            'source': 'serpapi'
        }


def search_similar_images_toolhouse(image_path):
    """Use Toolhouse to crawl and scrape for similar images"""

    if not TOOLHOUSE_API_KEY:
        return {'matches': [], 'total_found': 0, 'source': 'toolhouse'}

    try:
        # Convert image to base64 for Toolhouse API
        with open(image_path, 'rb') as img_file:
            image_base64 = base64.b64encode(img_file.read()).decode('utf-8')

        # Toolhouse API request for web scraping
        headers = {
            'Authorization': f'Bearer {TOOLHOUSE_API_KEY}',
            'Content-Type': 'application/json'
        }

        # Use Toolhouse's web scraping tools to find similar images
        payload = {
            'tool': 'web_scraper',
            'parameters': {
                'task': 'reverse_image_search',
                'image_data': image_base64,
                'search_engines': ['bing', 'yandex', 'tineye'],  # Alternative engines
                'max_results': 10,
                'include_metadata': True,
                'crawl_depth': 2  # How deep to crawl for additional sources
            }
        }

        response = requests.post(f'{TOOLHOUSE_BASE_URL}/tools/execute',
                                 json=payload, headers=headers)

        if response.status_code != 200:
            return {
                'matches': [],
                'total_found': 0,
                'error': f'Toolhouse API error: {response.status_code}',
                'source': 'toolhouse'
            }

        data = response.json()
        matches = []

        # Process Toolhouse results
        if 'results' in data and 'matches' in data['results']:
            for result in data['results']['matches'][:5]:
                matches.append({
                    'title': result.get('title', 'No title'),
                    'source': result.get('domain', 'Unknown source'),
                    'thumbnail': result.get('thumbnail_url', ''),
                    'link': result.get('page_url', ''),
                    'similarity': result.get('similarity_score', 'Medium'),
                    'search_engine': result.get('found_via', 'Toolhouse Scraper'),
                    'additional_info': result.get('metadata', {})
                })

        # Use Toolhouse to crawl specific sites for more matches
        additional_matches = crawl_image_sites_toolhouse(image_base64)
        matches.extend(additional_matches)

        return {
            'matches': matches,
            'total_found': len(matches),
            'source': 'toolhouse'
        }

    except Exception as e:
        return {
            'matches': [],
            'total_found': 0,
            'error': str(e),
            'source': 'toolhouse'
        }


def crawl_image_sites_toolhouse(image_base64):
    """Use Toolhouse to crawl specific image sharing sites"""

    # List of sites to crawl for similar images
    target_sites = [
        'pinterest.com',
        'flickr.com',
        'unsplash.com',
        'shutterstock.com',
        'getty images.com'
    ]

    additional_matches = []

    try:
        headers = {
            'Authorization': f'Bearer {TOOLHOUSE_API_KEY}',
            'Content-Type': 'application/json'
        }

        for site in target_sites:
            payload = {
                'tool': 'web_crawler',
                'parameters': {
                    'url': f'https://{site}',
                    'search_query': 'similar images',  # Would need to be more sophisticated
                    'image_comparison': image_base64,
                    'max_pages': 3,
                    'extract_images': True,
                    'similarity_threshold': 0.7
                }
            }

            response = requests.post(f'{TOOLHOUSE_BASE_URL}/tools/execute',
                                     json=payload, headers=headers)

            if response.status_code == 200:
                data = response.json()
                if 'results' in data and 'similar_images' in data['results']:
                    for img in data['results']['similar_images'][:2]:  # Limit per site
                        additional_matches.append({
                            'title': img.get('alt_text', f'Image from {site}'),
                            'source': site,
                            'thumbnail': img.get('thumbnail_url', ''),
                            'link': img.get('page_url', ''),
                            'similarity': img.get('similarity_score', 'Medium'),
                            'search_engine': f'Toolhouse Crawler ({site})'
                        })

    except Exception as e:
        print(f"Error crawling sites: {e}")

    return additional_matches


def combine_search_results(serpapi_results, toolhouse_results):
    """Combine and deduplicate results from different sources"""

    all_matches = []
    seen_urls = set()

    # Add SerpAPI results
    for match in serpapi_results.get('matches', []):
        url = match.get('link', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            all_matches.append(match)

    # Add Toolhouse results
    for match in toolhouse_results.get('matches', []):
        url = match.get('link', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            all_matches.append(match)

    # Sort by similarity or search engine preference
    def sort_key(match):
        similarity = match.get('similarity', 'Low')
        if similarity == 'High':
            return 0
        elif similarity == 'Medium':
            return 1
        else:
            return 2

    all_matches.sort(key=sort_key)

    return {
        'matches': all_matches,
        'total_found': len(all_matches),
        'serpapi_count': serpapi_results.get('total_found', 0),
        'toolhouse_count': toolhouse_results.get('total_found', 0),
        'errors': []
    }


# Enhanced endpoint for more detailed analysis
@app.route('/advanced-search', methods=['POST'])
def advanced_search():
    """More comprehensive search using Toolhouse's advanced features"""

    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    temp_path = os.path.join('uploads', file.filename)
    file.save(temp_path)

    try:
        # Convert image to base64
        with open(temp_path, 'rb') as img_file:
            image_base64 = base64.b64encode(img_file.read()).decode('utf-8')

        # Use Toolhouse for comprehensive analysis
        headers = {
            'Authorization': f'Bearer {TOOLHOUSE_API_KEY}',
            'Content-Type': 'application/json'
        }

        payload = {
            'tool': 'image_analyzer',
            'parameters': {
                'image_data': image_base64,
                'analysis_types': ['reverse_search', 'metadata_extraction', 'source_tracking'],
                'deep_web_search': True,
                'social_media_search': True,
                'stock_photo_search': True,
                'ai_generated_detection': True
            }
        }

        response = requests.post(f'{TOOLHOUSE_BASE_URL}/tools/execute',
                                 json=payload, headers=headers)

        os.remove(temp_path)

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Advanced analysis failed'}), 500

    except Exception as e:
        os.remove(temp_path)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    app.run(debug=True)