# Nominators

Nominators is a responsive Flask web application for managing rental properties. It is the browser-based version of the attached Real Estate Management System, replacing the Java Swing screens with role-based web dashboards.

## Included workflows

- Admin login, property approval/rejection, application review, and user statistics
- Property manager registration, property submission, portfolio view, and deletion
- Tenant registration, approved-property search, and property applications
- SQLite persistence with foreign keys, password hashing, and JSON property API
- Responsive landing page and dashboards

## Run locally

```bash
pip install -r requirements.txt
python main.py
```

Open `http://127.0.0.1:5000`. The database is created automatically on first run.

The seeded administrator is `admin` / `admin123`; change `SECRET_KEY` and the administrator credentials before production deployment. Set `DATABASE_PATH`, `SECRET_KEY`, `HOST`, `PORT`, and `FLASK_DEBUG` through environment variables as needed.

## API

`GET /api/properties` returns approved properties as JSON for integrations or a future mobile client.

## Tests

```bash
pytest tests/ -v
```
