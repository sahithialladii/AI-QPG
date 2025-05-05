from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session, make_response,send_file
import os
import mysql.connector
from dotenv import load_dotenv
import google.generativeai as genai
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from xhtml2pdf import pisa
from io import BytesIO
from ml.classify_students import classify_students
#from DB import get_user_papers



# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
UPLOAD_FOLDER ='uploads'
os.makedirs(UPLOAD_FOLDER,exist_ok=True)
app.secret_key = os.environ["SECRET_KEY"]  # Set your secret key for session management

# MySQL configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = os.environ["DB_PASSWORD"]
app.config['MYSQL_DB'] = os.environ["DB_NAME"]

# Connect to MySQL
db = mysql.connector.connect(
    host=app.config['MYSQL_HOST'],
    user=app.config['MYSQL_USER'],
    password=app.config['MYSQL_PASSWORD'],
    database=app.config['MYSQL_DB']
)





app.config['UPLOAD_FOLDER'] = 'uploads'  







# Configure the Gemini API
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Create the model with your desired configurations
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 512,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)

# Serve the welcome page
@app.route('/')
def welcome():
    return render_template('welcome.html')

# Serve the login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('login.html')

# Serve the registration page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        cursor = db.cursor()
        try:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, hashed_password))
            db.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            flash(f'Error: {err}', 'danger')
    
    return render_template('register.html')










# @app.route('/dashboard')
# def dashboard():
#     return render_template('dashboard.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')


@app.route('/upload_marksheet')
def upload_marksheet():
    return render_template('upload_marksheet.html')




@app.route('/previous_papers')
def previous_papers():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, title FROM question_papers WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
    papers = cursor.fetchall()

    return render_template('previous_papers.html', papers=papers)


# @app.route('/download_paper/<int:paper_id>')
# def download_paper(paper_id):
#     if 'user_id' not in session:
#         return redirect(url_for('login'))

#     user_id = session['user_id']
#     cursor = db.cursor(dictionary=True)
#     cursor.execute("SELECT file_path FROM question_papers WHERE id = %s AND user_id = %s", (paper_id, user_id))
#     paper = cursor.fetchone()

#     if paper:
#         return send_file(paper['file_path'], as_attachment=True)
#     else:
#         return "Paper not found or access denied", 404











from flask import send_file, Response

@app.route('/download_paper/<int:paper_id>')
def download_paper(paper_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT file_path FROM question_papers WHERE id = %s AND user_id = %s", (paper_id, session['user_id']))
    paper = cursor.fetchone()

    if not paper:
        return "File not found or unauthorized", 404

    return send_file(
        paper['file_path'],
        mimetype='application/pdf',
        as_attachment=False,  # <-- Important: Set to False to preview
        download_name='preview.pdf'  # Optional: browser-friendly name
    )









# @app.route('/upload', methods=['POST'])
# def upload():
#     if 'marksheet' not in request.files:
#         flash("No file part in the request.")
#         return redirect(request.url)

#     file = request.files['marksheet']
#     if file.filename == '':
#         flash("No file selected.")
#         return redirect(request.url)

#     if file:
#         filename = secure_filename(file.filename)
#         filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#         os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)  # Ensure folder exists
#         file.save(filepath)

#         try:
#             # Call your classification logic
#             classify_students(filepath)
#             flash("Marksheet uploaded and students classified successfully.")
#             return redirect(url_for('index'))  # Redirect to dashboard or next step
#         except Exception as e:
#             flash(f"Error during classification: {str(e)}")
#             return redirect(request.url)





@app.route('/upload', methods=['POST'])
def upload_file():
    if 'marksheet' not in request.files:
        return 'No file part'
    
    file = request.files['marksheet']
    if file.filename == '':
        return 'No selected file'
    if not file.filename.lower().endswith('.pdf'):
        return 'Only PDF files are allowed'
    
    threshold = float(request.form['threshold'])
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(save_path)

    try:
        group_A, group_B = classify_students(save_path, threshold)

        # Optional: Save CSVs
        group_A.to_csv('students_above_threshold.csv', index=False)
        group_B.to_csv('students_below_threshold.csv', index=False)

        # return f'''
        # <h3>Classification Successful!</h3>
        # <p><strong>{len(group_A)}</strong> students above or equal to threshold</p>
        # <p><strong>{len(group_B)}</strong> students below threshold</p>
        # <a href="/upload_marksheet">Upload Another</a>
        # '''
        return render_template('index.html', group_A=group_A.to_dict(orient='records'), group_B=group_B.to_dict(orient='records'))


    except Exception as e:
        return f'<h3>Error during classification:</h3><pre>{str(e)}</pre>'
    








# Serve the index page
@app.route('/index')
def index():
    return render_template('index.html', group_A=[], group_B=[])

@app.route('/generate_questions', methods=['POST'])
def generate_questions():
    data = request.get_json()
    topic = data.get('topic')
    num_questions = data.get('num_questions', 5)
    difficulty=data.get('difficulty')

    # Create the chat session for generating questions
    chat_session = model.start_chat(history=[
        {
            "role": "user",
            "parts": [f"Generate {num_questions} {difficulty} questions about {topic}."]
        }
    ])

    response = chat_session.send_message("INSERT_INPUT_HERE")

    # Extract questions from the response
    questions = response.text.strip().split('\n')

    return jsonify({"questions": questions})

#  # Route to generate the PDF
# @app.route('/generate_pdf', methods=['POST'])
# def generate_pdf():
#     data = request.get_json()
#     topic = data.get('topic')
#     questions = data.get('questions', [])

#     # Render the HTML template for the PDF
#     rendered_html = render_template(
#         'pdf_template.html',  # This is the template for the PDF
#         topic=topic,
#         questions=questions,
#         enumerate=enumerate  # Allows numbering in the template
#     )

#     # Create the PDF
#     pdf = BytesIO()
#     pisa_status = pisa.CreatePDF(BytesIO(rendered_html.encode('utf-8')), dest=pdf)

#     if pisa_status.err:
#         return jsonify({"error": "Error generating PDF"}), 500

#     # Send the PDF as a response
#     response = make_response(pdf.getvalue())
#     response.headers['Content-Type'] = 'application/pdf'
#     response.headers['Content-Disposition'] = f'attachment; filename={topic}_questions.pdf'
    
#     return response





@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    data = request.get_json()
    topic = data.get('topic')
    questions = data.get('questions', [])

    # Render the HTML template for the PDF
    rendered_html = render_template(
        'pdf_template.html',
        topic=topic,
        questions=questions,
        enumerate=enumerate
    )

    # Create the PDF in memory
    pdf = BytesIO()
    pisa_status = pisa.CreatePDF(BytesIO(rendered_html.encode('utf-8')), dest=pdf)

    if pisa_status.err:
        return jsonify({"error": "Error generating PDF"}), 500

    # Save the PDF to disk
    filename = f"{topic}_questions_{session['user_id']}.pdf"
    file_path = os.path.join("generated_papers", filename)
    os.makedirs("generated_papers", exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(pdf.getvalue())

    # Save metadata to DB
    try:
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO question_papers (user_id, title, file_path) VALUES (%s, %s, %s)",
            (session['user_id'], topic, file_path)
        )
        db.commit()
    except Exception as e:
        return jsonify({"error": f"DB insert failed: {str(e)}"}), 500

    # Send the PDF as a response
    response = make_response(pdf.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response







@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
