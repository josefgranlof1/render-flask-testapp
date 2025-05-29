# Project Setup

## Clone the repository
```bash
  git clone https://github.com/s1hetu/flask_app_security.git
```

## Create virtual environment
```bash
  python3 -m venv .venv
```

## Activate virtual environemt
```bash
  source .venv/bin/activate
```

## Install requirements
```bash
  pip install -r requirements.txt
```

## Set environment variables
- Check the `example.env` file, and create a `.env` file with same variables and their actual values.

## Perform DB Migrations
```bash
  flask db init
```
- This will create migrations directory in the root folder with versions directory, alembic.ini, env.py, etc.
- Open the env.py file and write `from src.models import UserData, UserPreference, UserImages, Match, Message, RelationshipData, Task`

```bash
  flask db migrate -m "commit_message"
```
- This creates the migration with commit message.
```bash
  flask db upgrade
```
- This applies the migrations

## Run application
```bash
  python app.py
```

### Code
- Encode/Decode password or JWT
  - Done
- env separation
  - Done
- Code Separation
  - Done
- routes with authentication
  - Done
- rate limits
  - Done
- Database and Migrations
  - Done
- CSRF and CORS
  - Done
- Logging
  - Done
- Sanitize (prevent SQLi, XSS)
- Add error handling and request failures with [] vs .get()
  - Done
  
### Deployment
- flask + gunicorn
  - Done
- dockerize
  - Done
- nginx
  - Done
- HTTPS



## Run from CLI
gunicorn -w 4 'app:create_app()'


### Nginx as a Reverse Proxy 
- Nginx will receive traffic on ports 80/443 and forward it to Gunicorn inside Docker.
`nginx.conf: /etc/nginx/sites-available/myapp/nginx.conf`
``` 
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;  # Gunicorn
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Redirect all HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
 
```

### Enable the config:
```commandline
sudo ln -s /etc/nginx/sites-available/myapp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### HTTPS (via Let’s Encrypt Certbot)
- Install certbot and get an SSL certificate. 
```commandline
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```
- Certbot will:
  - Get SSL certificates
  - Auto-update your Nginx config
  - Set up automatic renewals

- To test renewal:
  - sudo certbot renew --dry-run
