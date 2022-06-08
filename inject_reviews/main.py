import requests as rq
from datetime import datetime as dt
import time
import random
import logging
import os
from dotenv import load_dotenv

from resources.names import names
from resources.settings import BASE_URL, SPREE_PER_PAGE, MAX_REVIEWS, MINIMUN_REVIEW_WORDS 

load_dotenv()
logging.basicConfig(level=logging.DEBUG)


class InjectReviews:
    # Proxy
    PROXY_URL = os.getenv('PROXY_URL')

    # Spree
    SPREE_TOKEN = os.getenv('SPREE_TOKEN')
    SPREE_PER_PAGE = SPREE_PER_PAGE
    SPREE_HEADERS = {'X-Spree-Token': SPREE_TOKEN}
    PROXY = {
            "http": f"http://{PROXY_URL}",
            "https": f"http://{PROXY_URL}",
    }

    # Amazon Reviews API
    AMAZON_API_HEADERS = {
        'x-rapidapi-key': os.getenv('X-RAPIDAPI-KEY'),
        'x-rapidapi-host': os.getenv('X-RAPIDAPI-HOST')
    }

    # Google API
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

    # Base URL
    BASE_URL = BASE_URL

    # Limits:
    MAX_REVIEWS = MAX_REVIEWS
    MINIMUN_REVIEW_WORDS = MINIMUN_REVIEW_WORDS


    def get_spree_products(self):
        ''' Gets active products from Spree '''

        products = []

        # Mimics JSON response to start pagination
        rj = {
            'current_page': 0, 
            'pages': 1
        }

        while rj.get('current_page', 0) < rj.get('pages', 0):
            url = f"{self.BASE_URL}/api/v1/products/active_products?per_page={self.SPREE_PER_PAGE}&page={ rj['current_page'] + 1}"
            r = rq.get(url, headers = self.SPREE_HEADERS, proxies = self.PROXY)
            rj = r.json()

            for x in rj.get('products', []):
                if x.get('partnumber'):
                    products.append(x)

        return products

    def get_product_reviews(self, part_number):
        ''' Gets product reviews from external API service'''

        url = f'https://amazon-product-reviews-keywords.p.rapidapi.com/product/search?keyword={part_number}&country=US&category=aps'
        r = rq.get(url, headers=self.AMAZON_API_HEADERS)
        rj = r.json()

        if rj.get('totalProducts'):
            # Get reviews from first asin
            return self.get_asin_reviews(rj['products'][0]['asin'], part_number)


    def get_name(self):
        ''' Chooses random name '''
        return random.choice(names)

    def get_asin_reviews(self, asin, part_number):
        ''' Gets reviews from specific product asin '''

        url = f'https://amazon-product-reviews-keywords.p.rapidapi.com/product/reviews?country=US&category=aps&asin={asin}&page=1&variants=0'
        r = rq.get(url, headers=self.AMAZON_API_HEADERS)
        rj = r.json()

        reviews = []
        if rj.get('total_reviews'):
            rvs = rj.get('reviews', [])
            for rv in rvs:
                # Only accept reviews with a minimun amount of words
                if len(rv.get('review', '').split(' ')) >= self.MINIMUN_REVIEW_WORDS:

                    unix_ts = rv.get('date', {}).get('unix')
                    formated_ts = dt.utcfromtimestamp(unix_ts).strftime('%Y-%m-%d')
                    
                    reviews.append({
                        'part_number': part_number,
                        'date': formated_ts,
                        'name': self.get_name(),
                        'title': rv.get('title'),
                        'review': rv.get('review'),
                        'rating': rv.get('rating'),
                    })

                    if len(reviews) >= self.MAX_REVIEWS:
                        break

        return reviews


    def translate(self, query):
        ''' Translate reviews with google API translation services '''

        url = f'https://translation.googleapis.com/language/translate/v2?key={self.GOOGLE_API_KEY}&q={query}&target=es&alt=json&source=en'
        r = rq.get(url)
        rj = r.json()

        try:
            return rj.get('data',{}).get('translations')[0].get('translatedText')
        except Exception as e:
            logging.error(f'Translation error: {str(e)}') 
            return {}

    def translate_reviews(self, reviews):
        translated_reviews = []

        for review in reviews:
            translated_review = review.copy()
            translated_review.update({
                    'title': self.translate(review.get('title')),
                    'name': self.translate(review.get('name')),
                    'review': self.translate(review.get('review')) 
                })

            translated_reviews.append(translated_review)

        return translated_reviews

    def inject_spree(self, reviews, product_id):
        ''' Inject processed reviews into Spree '''
        for rv in reviews:
            payload = {
                "rating": rv.get('rating'),
                "name": rv.get('name'),
                "title": rv.get('title'),
                "review": rv.get('review'),
                "show_identifier": "1",
                "user_id": "32594",
                "product_id": product_id,
                "review_date": rv.get('date')
            }

            url = f"{self.BASE_URL}/api/reviews"
            r = rq.post(url, data=payload, headers=self.SPREE_HEADERS, proxies = self.PROXY)

            if r not in [200, 201]:
                logging.error(r.text)

            time.sleep(1)


    def run(self):
        logging.info('Started')

        ps = self.get_spree_products()

        for p in ps:
            try:
                product_id = p['id']
                part_number = p['partnumber']

                logging.info(f'Inserting {product_id} ...')

                reviews = self.get_product_reviews(part_number) 
                if reviews:
                    translated_reviews = self.translate_reviews(reviews)
                    self.inject_spree(translated_reviews, product_id)
            except Exception as e:
                logging.error(f'Error: {str(e)}')

        logging.info('All Done.')


if __name__ == '__main__':
    InjectReviews().run()

