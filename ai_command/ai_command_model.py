#!/usr/bin/env python3
"""Small supervised Japanese command classifier (FLICK/FIND/WAIT).

Usage:
  python3 ai_command_model.py --train
  python3 ai_command_model.py 'ピンクの丸いやつをやっつけろ！'
No robot is moved by this script.
"""
import argparse
from pathlib import Path
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

MODEL = Path(__file__).with_name('command_model.joblib')
EXAMPLES = {
    'FLICK': [
        'ピンクの丸いやつをやっつけろ', 'ピンクのボールを弾いて', 'ピンクボールを転がして',
        'ピンクの球を押して', 'ボールをはじいて', 'あのピンクの球を飛ばせ',
        'ピンクの玉を攻撃して', 'ピンクのボールを動かして', 'ピンクの丸いものを弾け',
        'ピンクの丸いやつをやっつけろ！', 'ピンクの球を転がせ', 'ピンクのボールを押して',
    ],
    'FIND': [
        'ピンクのボールを探して', 'ピンクボールはどこ', 'ピンクの球を見つけて',
        'ボールの位置を教えて', 'ピンクの丸いやつを探せ', 'ピンクの玉を認識して',
        'ピンクボールを検出して', 'ボールが見えるか確認して', 'ピンクの丸いものを見て',
        'ピンクのボールを探して！', 'ボールの場所を調べて', 'ピンクの球を見つけろ',
    ],
    'WAIT': [
        '何もしないで', '動かないで', 'そのまま待って', '停止して',
        '今は待機して', 'じっとしていて', '何もするな', '動作をやめて',
        '待っていて', '今は動かなくていい', '何もしないで！', 'しばらく待機',
    ],
}


def train():
    phrases = [p for group in EXAMPLES.values() for p in group]
    labels = [label for label, group in EXAMPLES.items() for _ in group]
    model = make_pipeline(
        TfidfVectorizer(analyzer='char', ngram_range=(1, 3), sublinear_tf=True),
        LogisticRegression(max_iter=1000, random_state=42),
    )
    model.fit(phrases, labels)
    joblib.dump(model, MODEL)
    print(f'Trained on {len(phrases)} examples; saved to {MODEL}')
    for text in ('ピンクの丸いやつをやっつけろ！', 'ピンクのボールを探して', '何もしないで'):
        print(f'{text} -> {model.predict([text])[0]}')


def predict(text):
    if not MODEL.exists():
        raise SystemExit('Model missing: run --train first')
    model = joblib.load(MODEL)
    scores = model.predict_proba([text])[0]
    i = scores.argmax()
    label, confidence = model.classes_[i], float(scores[i])
    print(f'{label} (confidence={confidence:.3f})')
    if confidence < 0.45:
        print('LOW CONFIDENCE: do not execute a robot action')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('text', nargs='?')
    parser.add_argument('--train', action='store_true')
    args = parser.parse_args()
    if args.train:
        train()
    elif args.text:
        predict(args.text)
    else:
        parser.error('Specify --train or a command string')
