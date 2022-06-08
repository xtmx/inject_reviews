# Reviews to Spree

This little app will inject and translate, with google translation services, reviews from an external API into Spree.

API URL: https://rapidapi.com/logicbuilder/api/amazon-product-reviews-keywords

### Settings
These files should be modified:

  **General settings:**
  ```
  inject_reviews/resources/settings.py
  ```

  **Sensible/private settings:**
  ```
  inject_reviews/env.env
  ```

### Run
```
python3 inject_reviews/main.py
```
