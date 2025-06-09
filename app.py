from flask import Flask, request, jsonify
import boto3
import os

app = Flask(__name__)

# Configuration (use environment variables or replace with actual values)
BEDROCK_REGION = os.environ.get("AWS_REGION", "us-east-2")
KB_ID = os.environ.get("BEDROCK_KB_ID", "MAKZOATKHX")
MODEL_ARN = os.environ.get("MODEL_ARN", "arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-3-haiku-20240307-v1:0")

# Create Bedrock Agent Runtime client
bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", region_name=BEDROCK_REGION)

@app.route("/")
def form():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Flask + Bedrock Chat</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 40px; background-color: #f0f2f5; }
            h2 { color: #333; }
            input[type=text] {
                width: 80%%;
                padding: 12px;
                margin: 8px 0;
                box-sizing: border-box;
                border: 2px solid #ccc;
                border-radius: 4px;
                font-size: 16px;
            }
            button {
                padding: 12px 20px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
            }
            button:hover {
                background-color: #45a049;
            }
            #response {
                margin-top: 20px;
                padding: 10px;
                border-radius: 4px;
                background-color: white;
                border: 1px solid #ccc;
            }
            #spinner {
                display: none;
                margin-left: 10px;
            }
        </style>
    </head>
    <body>
        <h2>Ask the AWS Bedrock Knowledge Base</h2>
        <input type="text" id="question" placeholder="Enter your question..." />
        <button onclick="submitForm()">Ask</button>
        <span id="spinner">⏳</span>
        <div id="response"></div>

        <script>
            function submitForm() {
                const question = document.getElementById("question").value;
                if (!question) {
                    alert("Please enter a question.");
                    return;
                }
                document.getElementById("spinner").style.display = "inline";
                document.getElementById("response").innerText = "";
                fetch('/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({question})
                })
                .then(res => res.json())
                .then(data => {
                    document.getElementById("spinner").style.display = "none";
                    document.getElementById("response").innerText = data.answer || data.error;
                })
                .catch(err => {
                    document.getElementById("spinner").style.display = "none";
                    document.getElementById("response").innerText = "Error: " + err.message;
                });
            }
        </script>
    </body>
    </html>
    '''

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
                    "modelArn": MODEL_ARN
                }
            }
        )
        answer = response['output']['text']
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
