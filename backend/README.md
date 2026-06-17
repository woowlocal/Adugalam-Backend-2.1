# Turf Backend Setup (Code + Database)

## 1) Import Database (MySQL)
### Windows
Run:
scripts\import_db.bat

### Linux/Mac
Run:
chmod +x scripts/import_db.sh
./scripts/import_db.sh

## 2) Install Python requirements
pip install -r requirements.txt

## 3) Run migrations (if needed)
python manage.py migrate

## 4) Start server
python manage.py runserver
