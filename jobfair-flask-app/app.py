from flask import Flask
from routes.views import views

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.secret_key = "your_secret_key"

app.register_blueprint(views)

if __name__ == "__main__":
    app.run(debug=True)
