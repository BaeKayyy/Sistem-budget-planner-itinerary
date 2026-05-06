import pandas as pd
import pickle

df = pd.read_csv("../data/processed/tfidf_dataset.csv")

with open("../data/processed/tfidf_vectorizer.pkl", "rb") as f:
    vectorizer = pickle.load(f)

with open("../data/processed/tfidf_matrix.pkl", "rb") as f:
    tfidf_matrix = pickle.load(f)