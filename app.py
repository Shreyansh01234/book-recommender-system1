from flask import Flask, render_template, request
import pickle
import numpy as np

top50= pickle.load(open("top_50.pkl","rb"))

app = Flask(__name__)
# def trim_to_50_words(text):
#     words=  text.split()
#     return ' '.join(words[:5])
# book_name=[]
# for i in list(top50['Book-Title'].values):
#     book_name.append(trim_to_50_words(i))


pt=pickle.load(open("pt.pkl",'rb'))
books=pickle.load(open("books.pkl",'rb'))
similarity=pickle.load(open("similarity.pkl",'rb'))


@app.route('/')
def index():
    return render_template('index.html',
                           book_name =list(top50['Book-Title'].values),
                           author=list(top50['Book-Author'].values),
                           image=list(top50['Image-URL-M'].values),
                           votes=list(top50['no-rating'].values),
                           rating=list(top50['avg-rating'].values)
    )

@app.route('/recommend')
def recommend_ui():
    return render_template('recommend.html')

@app.route('/recommend_books',methods=['post'])
def recommend():
    user_input= request.form.get('user_input')
    index=np.where(pt.index==user_input)
    a=sorted(list(enumerate(similarity[index[0][0]])),key=lambda x: x[1],reverse=True)[1:6]
    m=[]
    for i in range(5):
        l=[]
        temp=books[books['Book-Title']==pt.index[a[i][0]]]
        l.extend(temp.drop_duplicates('Book-Title')['Book-Title'])
        l.extend(temp.drop_duplicates('Book-Title')['Book-Author'])
        l.extend(temp.drop_duplicates('Book-Title')['Image-URL-M'])
        m.append(l)
    return render_template('recommend.html',data=m)

if __name__ == '__main__':
    app.run(debug=True)

