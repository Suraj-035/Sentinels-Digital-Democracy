from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

analyzer = SentimentIntensityAnalyzer()
text = "I love this project, it's amazing!"

score = analyzer.polarity_scores(text)
print(score)