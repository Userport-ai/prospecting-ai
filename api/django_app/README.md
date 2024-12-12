## Get started

1. Use a virtual environment. E.g.:
```shell
python3 -m venv usrprt-venv
pip install -r requirements.txt
```
2. Make sure to add it to `.gitignore` like below
```.gitignore
usrprt-venv/*
```
3. Install requirements
```shell
(usrprt-venv) sowrabh@Sowrabhs-MacBook-Pro django_app % pip install requirements.txt
```
4. (If running first time) Run migrations
```shell
python3 manage.py migrate
```
5. Run the server
```shell
python3 manage.py runserver
```
