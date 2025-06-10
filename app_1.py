import os
import json
import re
from flask import Flask, request, render_template, redirect, url_for, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from anthropic_llm import get_summary_with_context, get_entity_relationship_with_context, get_kop_doc
from utils import extract_text_from_pdf, parse_graph_data, markdown_to_docx
from db_models import db, Regulation, Upload, Summary, EntityGraph
from docx import Document
from io import BytesIO
import boto3

app = Flask(__name__)

BEDROCK_REGION = os.environ.get("AWS_REGION", "us-east-2")
KB_ID = os.environ.get("BEDROCK_KB_ID", "MAKZOATKHX")
MODEL_ARN = os.environ.get("MODEL_ARN","arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-3-haiku-20240307-v1:0")

# Create Bedrock Agent Runtime client
bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", region_name=BEDROCK_REGION)


    

@app.route("/ask", methods=["POST"])
def ask_question():
    data = request.get_json()
    question = data.get("question")
    
    if not question:
        return jsonify({"error": "Missing question"}), 400

    try:
        response = bedrock_agent_runtime.retrieve_and_generate(
            input={"text": question},
            retrieveAndGenerateConfiguration={
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": KB_ID,
                    "modelArn" : "arn:aws:bedrock:us-east-2:908924925940:inference-profile/us.anthropic.claude-3-haiku-20240307-v1:0"
                }
            }
        )
        answer = response['output']['text']
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Use SQLite database (local file-based)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///regulations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)



@app.route("/", methods=["GET", "POST"])
def index():
    regulations = Regulation.query.all()
    if request.method == "POST":
        regulation_id = request.form['regulation']
        mode = request.form.get('upload_mode')
        old_path = request.form.get('old_path', '').strip()
        new_path = request.form.get('new_path', '').strip()
        first_time_path = request.form.get('first_time_path', '').strip()

        if mode == "first_time":
            if not os.path.exists(first_time_path):
                return "New Regulation PDF path is invalid.", 400
            upload = Upload(regulation_id=regulation_id, old_path=None, new_path=first_time_path)
        else:
            if not (os.path.exists(old_path) and os.path.exists(new_path)):
                return "Old or New PDF path is invalid.", 400
            upload = Upload(regulation_id=regulation_id, old_path=old_path, new_path=new_path)

        db.session.add(upload)
        db.session.commit()
        process_upload(upload.id)
        return redirect(url_for("compare", upload_id=upload.id))

    return render_template("index.html", regulations=regulations)


@app.route("/compare/<int:upload_id>")
def compare(upload_id):
    return render_template("compare.html", upload_id=upload_id)


@app.route("/graph_data/<int:upload_id>/<version>")
def graph_data(upload_id, version):
    graph_entry = EntityGraph.query.filter_by(upload_id=upload_id).first()
    if not graph_entry:
        return jsonify({"nodes": [], "edges": []})
    if version == "old":
        return jsonify(json.loads(graph_entry.graph_old or '{}'))
    if version == "new":
        return jsonify(json.loads(graph_entry.graph_new or '{}'))
    return jsonify({"error": "Invalid version"}), 400


@app.route("/regenerate/<int:upload_id>", methods=["POST"])
def regenerate(upload_id):
    process_upload(upload_id)
    return redirect(url_for("compare", upload_id=upload_id))


@app.route("/approve/<int:upload_id>", methods=["POST"])
def approve(upload_id):
    summary = Summary.query.filter_by(upload_id=upload_id).first()
    graph = EntityGraph.query.filter_by(upload_id=upload_id).first()
    if not summary or not graph:
        return "Data not found", 404

    if not summary.new_summary or not graph.new_json:
        return "New data missing. Please upload new regulation first.", 400

    kop_text = get_kop_doc(new_summary=summary.new_summary, new_json_str=graph.new_json)
    doc = Document()
    doc.add_heading("Key Operating Procedure (KOP)", 0)
    markdown_to_docx(doc, kop_text)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"kop_upload_{upload_id}.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

@app.route("/chat")
def chat():
    return render_template("chat.html")
    
@app.route("/history")
def history():
    uploads = Upload.query.order_by(Upload.upload_time.desc()).all()
    return render_template("history.html", uploads=uploads)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        # Insert default regulations only if not already present
        if not Regulation.query.first():
            db.session.add_all([
                Regulation(name="EMIR Refit"),
                Regulation(name="MiFID II"),
                Regulation(name="SFTR"),
                Regulation(name="AWPR")
            ])
            db.session.commit()

    host = "0.0.0.0"
    port = 7000
    app.run(debug=True, host=host, port=port)
