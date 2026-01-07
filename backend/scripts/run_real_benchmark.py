import requests
import time
import sys
import json
import os
import string
import re
from collections import Counter

# API Configuration
API_URL = "http://127.0.0.1:8000/api/v1"
TOKEN_URL = f"{API_URL}/token"
QUERY_URL = f"{API_URL}/rag/query"
SQUAD_URL = "https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v1.1.json"
DATA_FILE = "data/squad_dev.json"

def normalize_answer(s):
    """Lower text and remove punctuation, articles and extra whitespace."""
    def remove_articles(text):
        return re.sub(r'\b(a|an|the)\b', ' ', text)

    def white_space_fix(text):
        return ' '.join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        return ''.join(ch for ch in text if ch not in exclude)

    def lower(text):
        return text.lower()

    return white_space_fix(remove_articles(remove_punc(lower(s))))

def f1_score(prediction, ground_truth):
    prediction_tokens = normalize_answer(prediction).split()
    ground_truth_tokens = normalize_answer(ground_truth).split()
    common = Counter(prediction_tokens) & Counter(ground_truth_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0
    precision = 1.0 * num_same / len(prediction_tokens)
    recall = 1.0 * num_same / len(ground_truth_tokens)
    f1 = (2 * precision * recall) / (precision + recall)
    return f1

def exact_match_score(prediction, ground_truth):
    return (normalize_answer(prediction) == normalize_answer(ground_truth))

def get_auth_token():
    try:
        response = requests.post(TOKEN_URL, data={"username": "admin", "password": "password"})
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            print(f"[ERROR] Auth Failed: {response.text}")
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Connection Error to {TOKEN_URL}: {e}")
        print("Ensure the uvicorn server is running!")
        sys.exit(1)

def run_benchmark(num_samples=5):
    # 1. Download Dataset if needed
    if not os.path.exists(DATA_FILE):
        print(f"Downloading SQuAD Dev Set from {SQUAD_URL}...")
        try:
            r = requests.get(SQUAD_URL)
            with open(DATA_FILE, 'wb') as f:
                f.write(r.content)
            print("Download Complete.")
        except Exception as e:
            print(f"Failed to download SQuAD: {e}")
            sys.exit(1)
            
    # 2. Parse Dataset
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        squad_data = json.load(f)
        
    print(f"Loaded SQuAD Data. Extracting first {num_samples} questions...")
    
    # Flatten SQuAD structure to list of (question, [answers])
    samples = []
    count = 0
    for article in squad_data['data']:
        for paragraph in article['paragraphs']:
            for qa in paragraph['qas']:
                if count >= num_samples:
                    break
                question = qa['question']
                answers = [a['text'] for a in qa['answers']]
                samples.append((question, answers))
                count += 1
            if count >= num_samples: break
        if count >= num_samples: break
        
    # 3. Authenticate
    print("Authenticating...")
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    scores = {"exact_match": [], "f1": []}
    
    print(f"\nRunning Benchmark on {len(samples)} REAL samples...")
    print("-" * 60)
    
    for i, (question, gold_answers) in enumerate(samples):
        # Query API
        try:
            start = time.time()
            resp = requests.post(QUERY_URL, json={"query": question, "top_k": 3}, headers=headers)
            latency = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                data = resp.json()
                pred_answer = data['answer']
                warning = data.get('warning', '')
            else:
                pred_answer = ""
                warning = f"HTTP {resp.status_code}"
                print(f"Request Failed: {resp.text}")

        except Exception as e:
            print(f"Error: {e}")
            pred_answer = ""
            warning = "Exception"

        # Calculate Scores
        em = max([exact_match_score(pred_answer, gt) for gt in gold_answers]) if gold_answers else 0
        f1 = max([f1_score(pred_answer, gt) for gt in gold_answers]) if gold_answers else 0
        
        scores["exact_match"].append(em)
        scores["f1"].append(f1)
        
        print(f"[{i+1}/{num_samples}] Q: {question[:60]}...")
        print(f"   Pred: {pred_answer[:60]}...")
        print(f"   Gold: {gold_answers[0][:60] if gold_answers else 'None'}...")
        if warning:
            print(f"   [WARN]: {warning}")
        print(f"   EM: {em} | F1: {f1:.2f} | Latency: {latency:.0f}ms\n")

    # Aggregate
    avg_em = sum(scores["exact_match"]) / len(scores["exact_match"])
    avg_f1 = sum(scores["f1"]) / len(scores["f1"])
    
    print("-" * 60)
    print("BENCHMARK RESULTS (On Real SQuAD Data)")
    print("-" * 60)
    print(f"Samples: {len(samples)}")
    print(f"Average Exact Match: {avg_em:.2%}")
    print(f"Average F1 Score:    {avg_f1:.2%}")
    print("-" * 60)

if __name__ == "__main__":
    run_benchmark(5)
