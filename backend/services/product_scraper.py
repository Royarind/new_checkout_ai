"""
Enhanced product scraper to extract thumbnail, price, ratings, and metadata from product URLs
Supports multiple e-commerce platforms with fallback strategies
"""

import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, List
import re
import json
from urllib.parse import urlparse
import asyncio
from concurrent.futures import ThreadPoolExecutor


class ProductScraper:
    """Multi-strategy product scraper with platform-specific extractors"""
    
    # Common headers to avoid blocking
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    @staticmethod
    def _extract_from_json_ld(soup: BeautifulSoup) -> Dict:
        """Extract data from JSON-LD structured data (most reliable)"""
        result = {}
        
        try:
            # Find all JSON-LD scripts
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    
                    # Handle list of JSON-LD objects
                    if isinstance(data, list):
                        for item in data:
                            result.update(ProductScraper._parse_json_ld_item(item))
                    else:
                        result.update(ProductScraper._parse_json_ld_item(data))
                        
                except json.JSONDecodeError:
                    continue
                    
        except Exception as e:
            print(f"[Scraper] JSON-LD extraction error: {e}")
        
        return result
    
    @staticmethod
    def _parse_json_ld_item(item: Dict) -> Dict:
        """Parse a single JSON-LD item"""
        result = {}
        
        item_type = item.get('@type', '')
        
        if item_type == 'Product' or 'Product' in str(item_type):
            # Product name
            if 'name' in item:
                result['title'] = item['name']
            
            # Image
            if 'image' in item:
                img = item['image']
                if isinstance(img, list):
                    result['thumbnail'] = img[0] if img else None
                elif isinstance(img, dict):
                    result['thumbnail'] = img.get('url') or img.get('@url')
                else:
                    result['thumbnail'] = img
            
            # Price
            if 'offers' in item:
                offers = item['offers']
                if isinstance(offers, dict):
                    price = offers.get('price') or offers.get('lowPrice')
                    currency = offers.get('priceCurrency', '')
                    if price:
                        result['price'] = f"{currency} {price}".strip()
                elif isinstance(offers, list) and offers:
                    price = offers[0].get('price')
                    currency = offers[0].get('priceCurrency', '')
                    if price:
                        result['price'] = f"{currency} {price}".strip()
            
            # Rating
            if 'aggregateRating' in item:
                rating_data = item['aggregateRating']
                rating_value = rating_data.get('ratingValue')
                review_count = rating_data.get('reviewCount') or rating_data.get('ratingCount')
                
                if rating_value:
                    result['rating'] = float(rating_value)
                if review_count:
                    result['review_count'] = int(review_count)
            
            # Brand
            if 'brand' in item:
                brand = item['brand']
                if isinstance(brand, dict):
                    result['brand'] = brand.get('name')
                else:
                    result['brand'] = brand
            
            # Availability
            if 'offers' in item:
                offers = item['offers']
                if isinstance(offers, dict):
                    availability = offers.get('availability', '')
                    result['in_stock'] = 'InStock' in availability
        
        return result
    
    @staticmethod
    def _extract_from_meta_tags(soup: BeautifulSoup) -> Dict:
        """Extract data from Open Graph and meta tags"""
        result = {}
        
        # Open Graph tags
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            result['thumbnail'] = og_image['content']
        
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            result['title'] = og_title['content']
        
        og_price = soup.find('meta', property='og:price:amount')
        if og_price and og_price.get('content'):
            og_currency = soup.find('meta', property='og:price:currency')
            currency = og_currency.get('content', '') if og_currency else ''
            result['price'] = f"{currency} {og_price['content']}".strip()
        
        # Twitter card tags (fallback)
        if not result.get('thumbnail'):
            twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                result['thumbnail'] = twitter_image['content']
        
        return result
    
    @staticmethod
    def _extract_from_html(soup: BeautifulSoup, url: str) -> Dict:
        """Extract data from HTML elements with common patterns"""
        result = {}
        
        # Title fallback
        if not result.get('title'):
            title_tag = soup.find('h1')
            if title_tag:
                result['title'] = title_tag.get_text(strip=True)
            elif soup.find('title'):
                result['title'] = soup.find('title').get_text(strip=True)
        
        # Price patterns (common selectors)
        if not result.get('price'):
            price_selectors = [
                {'class_': re.compile(r'price', re.I)},
                {'itemprop': 'price'},
                {'data-price': True},
                {'class_': re.compile(r'amount', re.I)},
            ]
            
            for selector in price_selectors:
                price_elem = soup.find(['span', 'div', 'p'], selector)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    # Extract price with currency symbol
                    price_match = re.search(r'[\$₹€£¥]\s*[\d,]+\.?\d*', price_text)
                    if price_match:
                        result['price'] = price_match.group()
                        break
        
        # Rating patterns
        if not result.get('rating'):
            rating_selectors = [
                {'class_': re.compile(r'rating', re.I)},
                {'itemprop': 'ratingValue'},
                {'data-rating': True},
            ]
            
            for selector in rating_selectors:
                rating_elem = soup.find(['span', 'div', 'meta'], selector)
                if rating_elem:
                    rating_text = rating_elem.get('content') or rating_elem.get_text(strip=True)
                    # Extract numeric rating
                    rating_match = re.search(r'\d+\.?\d*', rating_text)
                    if rating_match:
                        result['rating'] = float(rating_match.group())
                        break
        
        # Review count patterns
        if not result.get('review_count'):
            review_selectors = [
                {'class_': re.compile(r'review.*count', re.I)},
                {'itemprop': 'reviewCount'},
            ]
            
            for selector in review_selectors:
                review_elem = soup.find(['span', 'div', 'meta'], selector)
                if review_elem:
                    review_text = review_elem.get('content') or review_elem.get_text(strip=True)
                    # Extract number
                    review_match = re.search(r'[\d,]+', review_text)
                    if review_match:
                        result['review_count'] = int(review_match.group().replace(',', ''))
                        break
        
        # Image fallback (find largest product image)
        if not result.get('thumbnail'):
            img_tags = soup.find_all('img')
            best_img = None
            max_area = 0
            
            for img in img_tags:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                if not src or src.startswith('data:'):
                    continue
                
                # Prefer images with product keywords
                if any(keyword in src.lower() for keyword in ['product', 'item', 'image', 'photo']):
                    # Try to get image dimensions
                    width = img.get('width')
                    height = img.get('height')
                    
                    if width and height:
                        try:
                            area = int(width) * int(height)
                            if area > max_area:
                                max_area = area
                                best_img = src
                        except:
                            best_img = best_img or src
                    else:
                        best_img = best_img or src
            
            if best_img:
                # Make absolute URL if relative
                if best_img.startswith('//'):
                    best_img = 'https:' + best_img
                elif best_img.startswith('/'):
                    parsed = urlparse(url)
                    best_img = f"{parsed.scheme}://{parsed.netloc}{best_img}"
                
                result['thumbnail'] = best_img
        
        return result
    
    @staticmethod
    def _extract_platform_specific(soup: BeautifulSoup, url: str) -> Dict:
        """Platform-specific extraction logic"""
        result = {}
        domain = urlparse(url).netloc.lower()
        
        # Myntra
        if 'myntra.com' in domain:
            # Myntra uses specific class names
            price_elem = soup.find('span', class_=re.compile(r'pdp-price'))
            if price_elem:
                result['price'] = price_elem.get_text(strip=True)
            
            rating_elem = soup.find('div', class_=re.compile(r'rating'))
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                rating_match = re.search(r'\d+\.?\d*', rating_text)
                if rating_match:
                    result['rating'] = float(rating_match.group())
        
        # Amazon
        elif 'amazon' in domain:
            price_elem = soup.find('span', class_='a-price-whole')
            if price_elem:
                result['price'] = price_elem.get_text(strip=True)
            
            rating_elem = soup.find('span', class_='a-icon-alt')
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                rating_match = re.search(r'\d+\.?\d*', rating_text)
                if rating_match:
                    result['rating'] = float(rating_match.group())
        
        # Flipkart
        elif 'flipkart.com' in domain:
            price_elem = soup.find('div', class_=re.compile(r'_30jeq3'))
            if price_elem:
                result['price'] = price_elem.get_text(strip=True)
        
        # Shopify stores (generic pattern)
        elif soup.find('meta', attrs={'name': 'shopify-checkout-api-token'}):
            price_elem = soup.find('span', class_=re.compile(r'price'))
            if price_elem:
                result['price'] = price_elem.get_text(strip=True)
        
        return result


def extract_product_info(url: str, timeout: int = 10) -> Dict[str, Optional[str]]:
    """
    Extract product thumbnail, price, rating, and metadata from product URL
    Uses multiple strategies for maximum reliability
    
    Returns:
    {
        "thumbnail": "image_url",
        "title": "product_title",
        "price": "₹1,299" or "$49.99",
        "rating": 4.5,
        "review_count": 1234,
        "brand": "Brand Name",
        "in_stock": True
    }
    """
    print(f"[Product Scraper] Extracting info from: {url}")
    
    try:
        # Make request
        response = requests.get(
            url,
            headers=ProductScraper.HEADERS,
            timeout=timeout,
            allow_redirects=True
        )
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Strategy 1: JSON-LD (most reliable)
        print("[Product Scraper] Trying JSON-LD extraction...")
        result = ProductScraper._extract_from_json_ld(soup)
        
        # Strategy 2: Meta tags (Open Graph)
        print("[Product Scraper] Trying meta tags extraction...")
        meta_data = ProductScraper._extract_from_meta_tags(soup)
        for key, value in meta_data.items():
            if value and not result.get(key):
                result[key] = value
        
        # Strategy 3: Platform-specific extraction
        print("[Product Scraper] Trying platform-specific extraction...")
        platform_data = ProductScraper._extract_platform_specific(soup, url)
        for key, value in platform_data.items():
            if value and not result.get(key):
                result[key] = value
        
        # Strategy 4: Generic HTML patterns (fallback)
        print("[Product Scraper] Trying HTML pattern extraction...")
        html_data = ProductScraper._extract_from_html(soup, url)
        for key, value in html_data.items():
            if value and not result.get(key):
                result[key] = value
        
        # Ensure all expected keys exist
        final_result = {
            "thumbnail": result.get("thumbnail"),
            "title": result.get("title"),
            "price": result.get("price"),
            "rating": result.get("rating"),
            "review_count": result.get("review_count"),
            "brand": result.get("brand"),
            "in_stock": result.get("in_stock")
        }
        
        print(f"[Product Scraper] ✓ Extracted: {list(k for k, v in final_result.items() if v)}")
        return final_result
        
    except requests.Timeout:
        print(f"[Product Scraper] ⏱️ Timeout after {timeout}s")
        return _empty_result()
    except requests.RequestException as e:
        print(f"[Product Scraper] ❌ Request error: {e}")
        return _empty_result()
    except Exception as e:
        print(f"[Product Scraper] ❌ Unexpected error: {e}")
        import traceback
        print(traceback.format_exc())
        return _empty_result()


def _empty_result() -> Dict:
    """Return empty result dict"""
    return {
        "thumbnail": None,
        "title": None,
        "price": None,
        "rating": None,
        "review_count": None,
        "brand": None,
        "in_stock": None
    }


def get_product_thumbnail(url: str) -> Optional[str]:
    """Quick function to just get thumbnail"""
    info = extract_product_info(url)
    return info.get("thumbnail")


def get_product_title(url: str) -> Optional[str]:
    """Quick function to just get title"""
    info = extract_product_info(url)
    return info.get("title")


def get_product_price(url: str) -> Optional[str]:
    """Quick function to just get price"""
    info = extract_product_info(url)
    return info.get("price")


# Async version for better performance
async def extract_product_info_async(url: str, timeout: int = 10) -> Dict[str, Optional[str]]:
    """
    Async version of extract_product_info for use in async contexts
    """
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(
            executor,
            extract_product_info,
            url,
            timeout
        )
    return result


# Batch extraction for multiple URLs
async def extract_multiple_products(urls: List[str], timeout: int = 10) -> List[Dict]:
    """
    Extract info from multiple product URLs concurrently
    
    Returns:
        List of product info dicts in the same order as input URLs
    """
    tasks = [extract_product_info_async(url, timeout) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert exceptions to empty results
    return [
        result if not isinstance(result, Exception) else _empty_result()
        for result in results
    ]


# CLI testing
if __name__ == "__main__":
    # Test URLs
    test_urls = [
        "https://www.myntra.com/kurta-sets/varanga/varanga-ethnic-motifs-printed-zari-kurta-with-trouser--dupatta/36904064/buy",
        "https://www.amazon.com/dp/B08N5WRWNW",
        "https://www.flipkart.com/example-product"
    ]
    
    print("Testing product scraper...\n")
    
    for url in test_urls:
        print(f"\n{'='*80}")
        print(f"URL: {url}")
        print('='*80)
        
        info = extract_product_info(url)
        
        print(f"Title: {info['title']}")
        print(f"Price: {info['price']}")
        print(f"Rating: {info['rating']} ({info['review_count']} reviews)")
        print(f"Brand: {info['brand']}")
        print(f"In Stock: {info['in_stock']}")
        print(f"Thumbnail: {info['thumbnail'][:80] if info['thumbnail'] else None}...")



# """
# Product scraper to extract thumbnail and metadata from product URLs
# """

# import requests
# from bs4 import BeautifulSoup
# from typing import Optional, Dict
# import re


# def extract_product_info(url: str) -> Dict[str, Optional[str]]:
#     """
#     Extract product thumbnail and basic info from product URL
    
#     Returns:
#     {
#         "thumbnail": "image_url",
#         "title": "product_title",
#         "price": "price"
#     }
#     """
#     try:
#         headers = {
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
#         }
        
#         response = requests.get(url, headers=headers, timeout=10)
#         response.raise_for_status()
        
#         soup = BeautifulSoup(response.content, 'html.parser')
        
#         # Try to find Open Graph image (most common)
#         thumbnail = None
#         og_image = soup.find('meta', property='og:image')
#         if og_image and og_image.get('content'):
#             thumbnail = og_image['content']
        
#         # Fallback: try to find first product image
#         if not thumbnail:
#             img_tags = soup.find_all('img')
#             for img in img_tags:
#                 src = img.get('src') or img.get('data-src')
#                 if src and ('product' in src.lower() or 'item' in src.lower()):
#                     thumbnail = src
#                     break
        
#         # Get title
#         title = None
#         og_title = soup.find('meta', property='og:title')
#         if og_title and og_title.get('content'):
#             title = og_title['content']
#         elif soup.find('title'):
#             title = soup.find('title').text.strip()
        
#         # Get price (basic extraction)
#         price = None
#         price_meta = soup.find('meta', property='og:price:amount')
#         if price_meta and price_meta.get('content'):
#             price = price_meta['content']
        
#         return {
#             "thumbnail": thumbnail,
#             "title": title,
#             "price": price
#         }
        
#     except Exception as e:
#         print(f"[Product Scraper] Error extracting from {url}: {e}")
#         return {
#             "thumbnail": None,
#             "title": None,
#             "price": None
#         }


# def get_product_thumbnail(url: str) -> Optional[str]:
#     """Quick function to just get thumbnail"""
#     info = extract_product_info(url)
#     return info.get("thumbnail")
