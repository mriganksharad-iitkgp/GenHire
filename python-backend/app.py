from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from qa import PDFProcessor

app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

document_pdf_path = "Eric Ries - The Lean Startup.pdf"  # Path to the document for querying
groq_api_key = "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"  # Replace with actual API key
processor = PDFProcessor(document_pdf_path, groq_api_key)

@app.route('/api/answer_question', methods=['POST'])
@cross_origin()
def answer_question():
    data = request.json
    question = data.get('question')
    history = data.get('history')

    if question is None:
        return jsonify({'error': 'Missing question parameter'}), 400
    if history is None:
        history = {}
    
    # result = floods_qa_system.answer_question(question,history)

    result = processor.query_document(question)

    return jsonify({'result': str(result)})

if __name__ == '__main__':
    # app.run(debug=False,host='10.29.8.94')
    app.run(debug=True)