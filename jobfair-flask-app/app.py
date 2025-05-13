from flask import Flask, request, render_template
import pandas as pd

app = Flask(__name__)

def load_schedule():
    return pd.read_csv("schedule.csv")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        student_id = request.form["student_id"]
        df = load_schedule()
        row = df[df["student_id"] == student_id]
        return render_template("result.html", row=row)
    return render_template("index.html")

@app.route("/admin")
def admin():
    df = load_schedule()
    return render_template("admin.html", table=df.to_html(index=False))

if __name__ == "__main__":
    app.run(debug=True)
