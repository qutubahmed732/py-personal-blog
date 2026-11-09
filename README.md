# Personal Blog

A small Flask blog where visitors can read published articles and users can register, sign in, and manage their own posts.

## Features

- Browse articles and read individual posts
- Register and log in with securely hashed passwords
- Create, edit, and delete your own articles
- Save users and articles in a local JSON file

## Run locally

1. Install [Python](https://www.python.org/).
2. From the project folder, install the dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Start the app:

   ```powershell
   python app.py
   ```

4. Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

The app stores its data in `blog_data.json`.

## Challenge

Built as the [roadmap.sh Personal Blog project](https://roadmap.sh/projects/personal-blog).
