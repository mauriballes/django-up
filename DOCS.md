# Documentation for Django Up

I want give you a quick documentation about how to deploy your current app with django. Before we start, you need to know this project only work with django project with 2.0 version or greater and with python 3 on Unix based systems.

## Dependencies

You need to install the following dependecies

- Django >= 2.0
- gunicorn >= 19.9.0

## Install

You can find this package in `pypi` 

```bash
$ pip install django-up 
```

Then, you need to add this dependency in your django project:

```python
# ....
INSTALLED_APPS = [
    # Django Dependencies
    # .....

    # Django App
    'djangoup', # <=== You need to add this dependency

    # My Apps
    # .....
]
# ...
```

## How to Use

This installation add a new command to your django project. You can use the command: `python manage.py` and you can see a new option

```bash
...

[djangoup]
    deploy
    
...
```

1. First, you need to initialize your project config. Run the following command: 

```bash
$ python manage.py deploy --init
or
$ python manage.py deploy -i
```

This command will generate a file call: `deploy.yml`. You need to replace the following data:

```yaml
# Project Info
project_name: PROJECT_NAME_DJANGO # Project name for django project

# Repository
repo_url: git@github.com:USERNAME/PROJECT_NAME.git # Repo url project (It needs to be SSH)
branch: master # Branch for deploy
remote_name: origin # Remote server name

# Server
server_user: SERVER_USER # Username on server
server_ip: '12.34.56.78' # Server IP
server_ssh_port: 22
server_project_path: /home/SERVER_USER/apps/PROJECT_NAME # Path for your project on server (You can choose any place)
server_venv_path: /home/SERVER_USER/venvs/PROJECT_NAME # Path for your virtualenv on server (You can choose any place)

# Gunicorn
gunicorn_config_file: gunicorn.conf.py
gunicorn_bind: unix:/home/SERVER_USER/apps/PROJECT_NAME/PROJECT_NAME.sock # Path for gunicorn socket (You can choose any place)
gunicorn_pid_file: /home/SERVER_USER/apps/PROJECT_NAME/PROJECT_NAME.pid # Path for gunicorn pid (You can choose any place)
gunicorn_workers: 3 # Workers Recommended: (2 x $num_cores) + 1
gunicorn_worker_class: sync # Other options: http://docs.gunicorn.org/en/latest/settings.html#worker-class

# Python
python_runtime_venv: /usr/bin/python3 # Path for python interpreter

```

2. After fill the file `deploy.yml`, run the following command:

```bash
$ python manage.py deploy --build
or
$ python manage.py deploy -b
```

This will create a settings folder that will replace `settings.py` file. In that settings folder, you can copy the `base.py` and create two new files: `local.py` and `production.py`. This can help you to divide your local configuration and your production configuration.

Also, you have a new file call `gunicorn.conf.py`, this have 4 important values that are already replaced by data in `deploy.yml`. This values are:

```python
# Important Vars
bind = 'unix:/home/SERVER_USER/apps/PROJECT_NAME/PROJECT_NAME.sock'
workers = 3
worker_class = 'sync'
pidfile = '//home/SERVER_USER/apps/PROJECT_NAME/PROJECT_NAME.pid'
```

3. Finally, you need to deploy your project with the command:

```bash
$ python manage.py deploy
```

This will access to the server and run the app on the specific socket.

```
IMPORTANT NOTE

YOUR SSH KEY ON YOUR PROJECT REPOSITORY AND IN YOUR SERVER USER NEED TO BE THE SAME. THE NAME OF KEY NEED TO BE: id_rsa

THIS IS SOMETHING TO IMPROVE IN THE FUTURE, BUT TRY TO BE HAPPY BY THE MOMENT.
```

4. You need to configure your web server (apache or nginx) to handle the request to the gunicorn socket.

This is an example configuration on nginx

```Nginx
server {
    listen 80;
    server_name mydomain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    location /static/ {
        root /home/SERVER_USER/apps/PROJECT_NAME;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/SERVER_USER/apps/PROJECT_NAME/PROJECT_NAME.sock;
    }
}
```

5. Don't forget add your IP address or your domain to your django `ALLOWED_HOST` var in all your settings files.

## Credits

Please give me a star for the help and leave an issue if you have problems with the project.