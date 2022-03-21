# need python 3.7, no higher
# can only get tweets from within last 7 days du to restricted access
#
from fuzzywuzzy import fuzz
import easyocr
import tweepy
import config
from flask import Flask, render_template, request, redirect
import os
from werkzeug.utils import secure_filename
import imghdr

app = Flask(__name__)

app.static_folder = 'static'
# limit upload size to 10MB
app.config['MAX_CONTENT_LENGTH'] = 10 * 1000 * 1000
app.config['ALLOWED_EXTENSIONS'] = ['.JPG', '.JPEG', '.PNG']

if __name__ == '__main__':
    app.run(debug=True)

client = tweepy.Client(bearer_token=config.BEARER_TOKEN)


def tweet_search(input_img):
    # image processing, returns list of results, where each result is a list
    # with the recognised text at index 1
    reader = easyocr.Reader(["en"], gpu=False)
    results = reader.readtext(input_img)
    # if easyocr does not yield any results (i.e. no text recognised) return error code 1
    if not results:
        return 1
    # iterate over results and add all text to list, then turn list into string
    query = []
    for result in results:
        query.append(result[1])
    query = ' '.join(query)
    # tweet author will start at first '@' and end at first space after the '@'
    # first: check if '@' in query
    if '@' in query:
        author = query[query.index('@'):]
        author = author[:author.index(' ')]
        # but for tweepy to work, we actually have to exclude the '@' at the start of the author's username
        author = author[1:]
        # if author is found, use author as search query, otherwise just use whole query
        twitter_query = f"from:{author}"
    else:
        twitter_query = query
    tweets = tweepy.Paginator(client.search_recent_tweets, twitter_query, max_results=100).flatten(limit=250)
    # if twitter search does not yield any results, return error code 2
    if not tweets:
        return 2
    # iterate through returned tweets and find the one where difference between query and tweet.text is the smallest
    # i.e. desired tweet will be the one with the highest fuzz.ratio
    highest_score = 0
    for tweet in tweets:
        score = fuzz.ratio(tweet.text, query)
        tweet_list = tweet.text.split(" ")
        query_list = query.split(" ")
        # get number of matches between two lists
        num_common = len(list((set(tweet_list).intersection(query_list)))) / len(tweet_list) * 100
        # add to score
        score += num_common
        if score > highest_score:
            highest_score = score
            desired_tweet = tweet
    return f'https://twitter.com/anyuser/status/{desired_tweet.data["id"]}'




@app.route('/', methods=["GET", "POST"])
def show_home():
    if request.method == "POST":
        if request.files:
            image = request.files["image"]
            # secure filename
            # image content validation
            if not image:
                return "no image selected"
            # check if file extension valid
            filename = secure_filename(image.filename)
            img_ext = os.path.splitext(filename)[1]
            if img_ext.upper() not in app.config['ALLOWED_EXTENSIONS']:
                return "not allowed"
            # validate content to make sure img is actually img
            # read first 512 bytes of file to identify file format
            header = image.stream.read(512)
            # reset stream so that when image is saved, whole image is saved
            image.stream.seek(0)
            # get the format of the file
            file_format = imghdr.what(None, header)
            # if no format is found, abandon
            if not file_format:
                return "could not be validated"
            # if format is found, check that format is acceptable
            if "." + file_format.upper() not in app.config["ALLOWED_EXTENSIONS"]:
                return f"file has {img_ext} extension but is actually {file_format}"
            # finally, if all checks passed, save file
            image.save(f"./uploads/{filename}")
            # perform tweet search
            data = tweet_search(f"./uploads/{filename}")
            # delete file
            os.remove(f"./uploads/{filename}")
        if data == 1:
            return render_template('fail.html', data="No text found in image")
        if data == 2:
            return render_template('fail.html', data="tweet could not be found")
        return redirect(data)
    return render_template('index.html')
