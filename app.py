from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from functools import wraps
import os
import uuid
from datetime import datetime
from urllib.parse import urlparse
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import DATABASE_CONFIG, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['COVER_UPLOAD_FOLDER'] = os.path.join('static', 'uploads', 'covers')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

os.makedirs(app.config['COVER_UPLOAD_FOLDER'], exist_ok=True)


def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def save_cover_image(file_storage):
    if not file_storage or file_storage.filename == '':
        return None

    if not file_storage.mimetype or not file_storage.mimetype.startswith('image/'):
        return None

    if not allowed_image(file_storage.filename):
        return None

    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    base_name = secure_filename(file_storage.filename.rsplit('.', 1)[0]) or 'cover'
    final_name = f"{base_name}-{uuid.uuid4().hex[:10]}.{ext}"
    full_path = os.path.join(app.config['COVER_UPLOAD_FOLDER'], final_name)
    file_storage.save(full_path)
    return f"uploads/covers/{final_name}"


def is_valid_cover_url(cover_url):
    if not cover_url:
        return False
    parsed = urlparse(cover_url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return False
    return allowed_image(parsed.path.lower())


@app.template_filter('cover_src')
def cover_src(path):
    if not path:
        return ''
    if path.startswith('http://') or path.startswith('https://'):
        return path
    return url_for('static', filename=path)


def get_db_connection():
    return psycopg2.connect(**DATABASE_CONFIG)


def create_notification(cur, user_id, message):
    cur.execute(
        'INSERT INTO notifications (user_id, message) VALUES (%s, %s)',
        (user_id, message)
    )


@app.context_processor
def inject_notification_count():
    theme = session.get('ui_theme', 'light')
    if theme not in ('light', 'dark'):
        theme = 'light'

    if 'user_id' not in session:
        return {'unread_notifications_count': 0, 'ui_theme': theme}

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    unread_count = 0
    try:
        cur.execute('''
            SELECT COUNT(*) AS unread_count
            FROM notifications
            WHERE user_id = %s AND is_read = FALSE
        ''', (session['user_id'],))
        unread_count = cur.fetchone()['unread_count']
    except psycopg2.Error:
        unread_count = 0
    finally:
        cur.close()
        conn.close()

    return {'unread_notifications_count': unread_count, 'ui_theme': theme}


@app.route('/theme/<string:theme>')
def set_theme(theme):
    if theme not in ('light', 'dark'):
        theme = 'light'
    session['ui_theme'] = theme

    next_url = request.args.get('next', '').strip()
    if next_url:
        parsed = urlparse(next_url)
        if not parsed.netloc and next_url.startswith('/'):
            return redirect(next_url)
    if request.referrer:
        return redirect(request.referrer)
    return redirect(url_for('home'))


@app.route('/theme', methods=['POST'])
def set_theme_toggle():
    theme = 'dark' if request.form.get('theme') == 'dark' else 'light'
    session['ui_theme'] = theme

    next_url = request.form.get('next', '').strip()
    if next_url:
        parsed = urlparse(next_url)
        if not parsed.netloc and next_url.startswith('/'):
            return redirect(next_url)
    if request.referrer:
        return redirect(request.referrer)
    return redirect(url_for('home'))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function


def get_story_filters():
    search_query = request.args.get('q', '', type=str).strip()
    genre = request.args.get('genre', '', type=str).strip()
    sort = request.args.get('sort', 'latest', type=str).strip().lower()
    page = request.args.get('page', 1, type=int)
    per_page = 12
    if page < 1:
        page = 1
    return search_query, genre, sort, page, per_page


def build_discovery_where(search_query='', genre=''):
    where_clauses = ['s.is_published = TRUE']
    where_params = []

    if search_query:
        where_clauses.append('s.title ILIKE %s')
        where_params.append(f'%{search_query}%')

    if genre:
        where_clauses.append('g.genre_name = %s')
        where_params.append(genre)

    return ' AND '.join(where_clauses), where_params


def fetch_story_cards(cur, where_sql, where_params, order_by, limit, offset=0):
    stories_query = f'''
        SELECT
            s.story_id,
            s.title,
            s.cover_image,
            s.view_count,
            s.created_at,
            u.username AS author_name,
            g.genre_name,
            COALESCE(MAX(c.published_at), s.published_at, s.created_at) AS latest_update,
            COUNT(DISTINCT c.chapter_id) AS chapter_count,
            COUNT(DISTINCT sf.user_id) AS follower_count
        FROM stories s
        JOIN users u ON s.author_id = u.user_id
        JOIN genres g ON s.genre_id = g.genre_id
        LEFT JOIN chapters c
               ON s.story_id = c.story_id
              AND c.status = 'published'
              AND c.published_at <= CURRENT_TIMESTAMP
        LEFT JOIN story_follows sf ON s.story_id = sf.story_id
        WHERE {where_sql}
        GROUP BY s.story_id, u.username, g.genre_name
        ORDER BY {order_by}
        LIMIT %s OFFSET %s
    '''
    cur.execute(stories_query, tuple(where_params + [limit, offset]))
    return cur.fetchall()


def count_discovery_stories(cur, where_sql, where_params):
    count_query = f'''
        SELECT COUNT(*) AS total
        FROM stories s
        JOIN users u ON s.author_id = u.user_id
        JOIN genres g ON s.genre_id = g.genre_id
        WHERE {where_sql}
    '''
    cur.execute(count_query, tuple(where_params))
    return cur.fetchone()['total']


def fetch_latest_updates(cur, limit=6):
    where_sql, where_params = build_discovery_where()
    return fetch_story_cards(
        cur,
        where_sql,
        where_params,
        order_by='latest_update DESC, s.story_id DESC',
        limit=limit
    )


def fetch_popular_stories(cur, limit=6):
    where_sql, where_params = build_discovery_where()
    return fetch_story_cards(
        cur,
        where_sql,
        where_params,
        order_by='follower_count DESC, s.view_count DESC, latest_update DESC, s.story_id DESC',
        limit=limit
    )


def fetch_newly_added_stories(cur, limit=6):
    where_sql, where_params = build_discovery_where()
    return fetch_story_cards(
        cur,
        where_sql,
        where_params,
        order_by='s.created_at DESC, s.story_id DESC',
        limit=limit
    )


def fetch_trending_stories(cur, limit=6):
    # Trending is computed dynamically from a 7-day rolling engagement window.
    # Score formula:
    # (recent_follows * 3) + (recent_chapters * 2) + average_rating
    # Ratings are intentionally lower-weight than follows/chapter updates.
    cur.execute('''
        SELECT
            s.story_id,
            s.title,
            s.cover_image,
            u.username AS author_name,
            g.genre_name,
            COALESCE(rf.recent_follows, 0) AS recent_follows,
            COALESCE(rc.recent_chapters, 0) AS recent_chapters,
            ROUND(COALESCE(ar.avg_rating, 0), 2) AS avg_rating,
            (
                COALESCE(rf.recent_follows, 0) * 3
                + COALESCE(rc.recent_chapters, 0) * 2
                + COALESCE(ar.avg_rating, 0)
            ) AS trending_score
        FROM stories s
        JOIN users u ON s.author_id = u.user_id
        JOIN genres g ON s.genre_id = g.genre_id
        LEFT JOIN (
            SELECT story_id, COUNT(*) AS recent_follows
            FROM story_follows
            WHERE created_at >= NOW() - INTERVAL '7 days'
            GROUP BY story_id
        ) rf ON s.story_id = rf.story_id
        LEFT JOIN (
            SELECT story_id, COUNT(*) AS recent_chapters
            FROM chapters
            WHERE status = 'published'
              AND published_at <= NOW()
              AND published_at >= NOW() - INTERVAL '7 days'
            GROUP BY story_id
        ) rc ON s.story_id = rc.story_id
        LEFT JOIN (
            SELECT story_id, AVG(rating)::numeric AS avg_rating
            FROM ratings
            GROUP BY story_id
        ) ar ON s.story_id = ar.story_id
        WHERE s.is_published = TRUE
        ORDER BY
            trending_score DESC,
            COALESCE(rf.recent_follows, 0) DESC,
            COALESCE(rc.recent_chapters, 0) DESC,
            s.story_id DESC
        LIMIT %s
    ''', (limit,))
    return cur.fetchall()


def fetch_story_discovery_page(cur, search_query, genre, sort, page, per_page):
    allowed_sorts = {
        'latest': 'latest_update DESC, s.story_id DESC',
        'popular': 'follower_count DESC, s.view_count DESC, latest_update DESC, s.story_id DESC',
        'most_favorited': 'follower_count DESC, latest_update DESC, s.story_id DESC'
    }
    sort = sort if sort in allowed_sorts else 'latest'
    where_sql, where_params = build_discovery_where(search_query, genre)

    total_stories = count_discovery_stories(cur, where_sql, where_params)
    total_pages = max(1, (total_stories + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages

    offset = (page - 1) * per_page
    stories = fetch_story_cards(
        cur,
        where_sql,
        where_params,
        order_by=allowed_sorts[sort],
        limit=per_page,
        offset=offset
    )
    return stories, sort, page, total_pages


def fetch_continue_reading(cur, user_id, limit=5):
    cur.execute('''
        SELECT
            s.story_id,
            s.title,
            s.cover_image,
            u.username AS author_name,
            g.genre_name,
            h.last_chapter_id,
            c.chapter_number AS last_chapter_number,
            c.title AS last_chapter_title,
            h.last_read_at
        FROM reading_history h
        JOIN stories s ON h.story_id = s.story_id
        JOIN users u ON s.author_id = u.user_id
        JOIN genres g ON s.genre_id = g.genre_id
        JOIN chapters c ON h.last_chapter_id = c.chapter_id
        WHERE h.user_id = %s AND s.is_published = TRUE
          AND c.status = 'published'
          AND c.published_at <= CURRENT_TIMESTAMP
        ORDER BY h.last_read_at DESC
        LIMIT %s
    ''', (user_id, limit))
    return cur.fetchall()


def upsert_reading_history(cur, user_id, story_id, chapter_id):
    cur.execute('''
        INSERT INTO reading_history (user_id, story_id, last_chapter_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id, story_id)
        DO UPDATE SET
            last_chapter_id = EXCLUDED.last_chapter_id,
            last_read_at = CURRENT_TIMESTAMP
    ''', (user_id, story_id, chapter_id))


@app.route('/')
def home():
    search_query, genre, sort, page, per_page = get_story_filters()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    latest_updates = fetch_latest_updates(cur, limit=6)
    trending_stories = fetch_trending_stories(cur, limit=6)
    popular_stories = fetch_popular_stories(cur, limit=6)
    newly_added = fetch_newly_added_stories(cur, limit=6)
    continue_reading = []
    if 'user_id' in session:
        continue_reading = fetch_continue_reading(cur, session['user_id'], limit=5)

    search_results = []
    total_pages = 1
    if search_query or genre or sort != 'latest' or page > 1:
        search_results, sort, page, total_pages = fetch_story_discovery_page(
            cur, search_query, genre, sort, page, per_page
        )

    cur.close()
    conn.close()

    return render_template(
        'home.html',
        latest_updates=latest_updates,
        trending_stories=trending_stories,
        popular_stories=popular_stories,
        newly_added=newly_added,
        continue_reading=continue_reading,
        search_results=search_results,
        filters={'q': search_query, 'genre': genre, 'sort': sort},
        page=page,
        total_pages=total_pages
    )


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # Unified user system: all users register once; authorship is behavior-based.
            cur.execute('''
                INSERT INTO users (username, email, password_hash, is_author)
                VALUES (%s, %s, %s, FALSE)
            ''', (username, email, hashed_password))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except psycopg2.Error:
            conn.rollback()
            flash('Registration failed. Username or email may already exist.', 'error')
        finally:
            cur.close()
            conn.close()

    return render_template('register.html')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not username or not email or not new_password:
            flash('All fields are required.', 'error')
            return render_template('forgot_password.html')

        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('forgot_password.html')

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                'SELECT user_id FROM users WHERE username = %s AND email = %s',
                (username, email)
            )
            user = cur.fetchone()
            if not user:
                flash('No account matches that username and email.', 'error')
                return render_template('forgot_password.html')

            hashed_password = generate_password_hash(new_password)
            cur.execute(
                'UPDATE users SET password_hash = %s WHERE user_id = %s',
                (hashed_password, user['user_id'])
            )
            conn.commit()
            flash('Password reset successful. Please log in.', 'success')
            return redirect(url_for('login'))
        except psycopg2.Error:
            conn.rollback()
            flash('Failed to reset password.', 'error')
        finally:
            cur.close()
            conn.close()

    return render_template('forgot_password.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('''
            SELECT u.user_id, u.username, u.password_hash, u.is_author, u.avatar_url,
                   COALESCE(r.role_name, '') AS role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.role_id
            WHERE u.username = %s
        ''', (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['is_author'] = user['is_author']
            session['is_admin'] = user['role_name'] == 'admin'
            session['avatar_url'] = user.get('avatar_url')
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))


@app.route('/story/<int:story_id>')
def view_story(story_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('''
        SELECT
            s.story_id,
            s.title,
            s.description,
            s.cover_image,
            s.view_count,
            s.created_at,
            s.author_id,
            s.genre_id,
            u.username AS author_name,
            g.genre_name,
            COUNT(DISTINCT c.chapter_id) AS chapter_count,
            COUNT(DISTINCT sf.user_id) AS follower_count,
            ROUND(COALESCE(AVG(r.rating), 0), 2) AS avg_rating
        FROM stories s
        JOIN users u ON s.author_id = u.user_id
        JOIN genres g ON s.genre_id = g.genre_id
        LEFT JOIN chapters c
               ON s.story_id = c.story_id
              AND c.status = 'published'
              AND c.published_at <= CURRENT_TIMESTAMP
        LEFT JOIN story_follows sf ON s.story_id = sf.story_id
        LEFT JOIN ratings r ON s.story_id = r.story_id
        WHERE s.story_id = %s AND s.is_published = TRUE
        GROUP BY s.story_id, u.username, g.genre_name
    ''', (story_id,))
    story = cur.fetchone()

    if not story:
        flash('Story not found.', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('home'))

    cur.execute('UPDATE stories SET view_count = view_count + 1 WHERE story_id = %s', (story_id,))
    conn.commit()
    story['view_count'] += 1

    is_author_view = 'user_id' in session and story['author_id'] == session['user_id']
    if is_author_view:
        cur.execute('''
            SELECT chapter_id, chapter_number, title, status, published_at, created_at
            FROM chapters
            WHERE story_id = %s
            ORDER BY chapter_number
        ''', (story_id,))
    else:
        cur.execute('''
            SELECT chapter_id, chapter_number, title, status, published_at, created_at
            FROM chapters
            WHERE story_id = %s
              AND status = 'published'
              AND published_at <= CURRENT_TIMESTAMP
            ORDER BY chapter_number
        ''', (story_id,))
    chapters = cur.fetchall()
    story['chapter_count'] = len(chapters)
    chapter_lookup = {chapter['chapter_id']: chapter for chapter in chapters}

    current_chapter_id = request.args.get('chapter', type=int)
    if current_chapter_id and current_chapter_id not in chapter_lookup:
        current_chapter_id = None

    user_rating = None
    user_review = None
    last_read_chapter_id = None
    is_following = False
    can_edit_story = False
    can_reply_as_author = False
    can_review = False
    if 'user_id' in session:
        cur.execute(
            'SELECT rating FROM ratings WHERE story_id = %s AND user_id = %s',
            (story_id, session['user_id'])
        )
        rating_row = cur.fetchone()
        if rating_row:
            user_rating = rating_row['rating']

        cur.execute(
            'SELECT 1 FROM story_follows WHERE story_id = %s AND user_id = %s',
            (story_id, session['user_id'])
        )
        is_following = cur.fetchone() is not None
        can_reply_as_author = story['author_id'] == session['user_id']
        can_edit_story = story['author_id'] == session['user_id']
        can_review = story['author_id'] != session['user_id']

        cur.execute('''
            SELECT review_id, title, body, rating, created_at, updated_at
            FROM story_reviews
            WHERE story_id = %s AND user_id = %s
        ''', (story_id, session['user_id']))
        user_review = cur.fetchone()

        cur.execute('''
            SELECT last_chapter_id
            FROM reading_history
            WHERE user_id = %s AND story_id = %s
        ''', (session['user_id'], story_id))
        history_row = cur.fetchone()
        if history_row:
            last_read_chapter_id = history_row['last_chapter_id']

    cur.execute('''
        SELECT
            sr.review_id,
            sr.user_id,
            sr.title,
            sr.body,
            sr.rating,
            sr.created_at,
            sr.updated_at,
            u.username
        FROM story_reviews sr
        JOIN users u ON sr.user_id = u.user_id
        WHERE sr.story_id = %s
        ORDER BY sr.created_at DESC
    ''', (story_id,))
    reviews = cur.fetchall()

    cur.execute('''
        SELECT
            s.story_id,
            s.title,
            s.cover_image,
            u.username AS author_name,
            g.genre_name,
            COALESCE(shared.shared_followers, 0) AS shared_followers,
            CASE WHEN s.genre_id = %s THEN 1 ELSE 0 END AS shared_genre
        FROM stories s
        JOIN users u ON s.author_id = u.user_id
        JOIN genres g ON s.genre_id = g.genre_id
        LEFT JOIN (
            SELECT
                sf_candidate.story_id,
                COUNT(*) AS shared_followers
            FROM story_follows sf_current
            JOIN story_follows sf_candidate
              ON sf_candidate.user_id = sf_current.user_id
            WHERE sf_current.story_id = %s
              AND sf_candidate.story_id <> %s
            GROUP BY sf_candidate.story_id
        ) shared ON shared.story_id = s.story_id
        WHERE s.is_published = TRUE
          AND s.story_id <> %s
          AND (s.genre_id = %s OR COALESCE(shared.shared_followers, 0) > 0)
        ORDER BY
            (CASE WHEN s.genre_id = %s THEN 2 ELSE 0 END + COALESCE(shared.shared_followers, 0)) DESC,
            COALESCE(shared.shared_followers, 0) DESC,
            s.view_count DESC,
            s.story_id DESC
        LIMIT 4
    ''', (
        story['genre_id'],
        story_id,
        story_id,
        story_id,
        story['genre_id'],
        story['genre_id']
    ))
    similar_stories = cur.fetchall()

    cur.close()
    conn.close()

    first_chapter = chapters[0] if chapters else None
    return render_template(
        'story.html',
        story=story,
        chapters=chapters,
        first_chapter=first_chapter,
        current_chapter_id=current_chapter_id,
        last_read_chapter_id=last_read_chapter_id,
        user_rating=user_rating,
        user_review=user_review,
        reviews=reviews,
        similar_stories=similar_stories,
        can_review=can_review,
        can_edit_story=can_edit_story,
        is_following=is_following,
        can_reply_as_author=can_reply_as_author,
        now_utc=datetime.utcnow()
    )


@app.route('/chapter/<int:chapter_id>', methods=['GET', 'POST'])
def view_chapter(chapter_id):
    # Reading mode preference is persisted in session for both guests and logged-in users.
    allowed_font_sizes = {16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40}
    requested_font_size = request.args.get('font_size', type=int)
    if requested_font_size in allowed_font_sizes:
        session['reading_font_size'] = requested_font_size
    reading_font_size = session.get('reading_font_size', 20)
    if not isinstance(reading_font_size, int) or reading_font_size not in allowed_font_sizes:
        reading_font_size = 20
    reading_line_height = 1.95 if reading_font_size <= 22 else (1.85 if reading_font_size <= 30 else 1.75)

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('''
        SELECT
            c.chapter_id,
            c.story_id,
            c.chapter_number,
            c.title AS chapter_title,
            c.content,
            c.status,
            c.published_at,
            c.created_at,
            s.title AS story_title,
            s.author_id,
            s.is_published,
            u.username AS author_name
        FROM chapters c
        JOIN stories s ON c.story_id = s.story_id
        JOIN users u ON s.author_id = u.user_id
        WHERE c.chapter_id = %s
    ''', (chapter_id,))
    chapter = cur.fetchone()

    if not chapter:
        cur.close()
        conn.close()
        abort(404)

    is_author_view = 'user_id' in session and chapter['author_id'] == session['user_id']
    chapter_is_public = (
        chapter['is_published']
        and chapter['status'] == 'published'
        and chapter['published_at'] is not None
        and chapter['published_at'] <= datetime.utcnow()
    )
    if not is_author_view and not chapter_is_public:
        cur.close()
        conn.close()
        abort(404)

    if request.method == 'POST':
        if 'user_id' not in session:
            cur.close()
            conn.close()
            abort(404)
        if not is_author_view:
            cur.close()
            conn.close()
            abort(404)

        updated_content = request.form.get('content', '').strip()
        if not updated_content:
            flash('Chapter content is required.', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('view_chapter', chapter_id=chapter_id, edit=1))

        try:
            cur.execute(
                'UPDATE chapters SET content = %s WHERE chapter_id = %s',
                (updated_content, chapter_id)
            )
            conn.commit()
            flash('Chapter updated successfully.', 'success')
            chapter['content'] = updated_content
        except psycopg2.Error:
            conn.rollback()
            flash('Failed to update chapter.', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('view_chapter', chapter_id=chapter_id, edit=1))

        cur.close()
        conn.close()
        return redirect(url_for('view_chapter', chapter_id=chapter_id))

    if is_author_view:
        cur.execute('''
            SELECT chapter_id
            FROM chapters
            WHERE story_id = %s AND chapter_number < %s
            ORDER BY chapter_number DESC
            LIMIT 1
        ''', (chapter['story_id'], chapter['chapter_number']))
        prev_row = cur.fetchone()

        cur.execute('''
            SELECT chapter_id
            FROM chapters
            WHERE story_id = %s AND chapter_number > %s
            ORDER BY chapter_number ASC
            LIMIT 1
        ''', (chapter['story_id'], chapter['chapter_number']))
        next_row = cur.fetchone()
    else:
        cur.execute('''
            SELECT chapter_id
            FROM chapters
            WHERE story_id = %s
              AND status = 'published'
              AND published_at <= CURRENT_TIMESTAMP
              AND chapter_number < %s
            ORDER BY chapter_number DESC
            LIMIT 1
        ''', (chapter['story_id'], chapter['chapter_number']))
        prev_row = cur.fetchone()

        cur.execute('''
            SELECT chapter_id
            FROM chapters
            WHERE story_id = %s
              AND status = 'published'
              AND published_at <= CURRENT_TIMESTAMP
              AND chapter_number > %s
            ORDER BY chapter_number ASC
            LIMIT 1
        ''', (chapter['story_id'], chapter['chapter_number']))
        next_row = cur.fetchone()

    cur.execute('''
        SELECT
            cc.comment_id,
            cc.user_id,
            cc.parent_comment_id,
            cc.content,
            cc.created_at,
            u.username
        FROM chapter_comments cc
        JOIN users u ON cc.user_id = u.user_id
        WHERE cc.chapter_id = %s
        ORDER BY cc.created_at DESC
    ''', (chapter_id,))
    chapter_comments = cur.fetchall()

    root_comments = []
    replies_by_parent = {}
    for comment in chapter_comments:
        if comment['parent_comment_id']:
            replies_by_parent.setdefault(comment['parent_comment_id'], []).append(comment)
        else:
            root_comments.append(comment)
    for comment in root_comments:
        comment['replies'] = replies_by_parent.get(comment['comment_id'], [])

    can_edit_chapter = False
    can_reply_as_author = False
    edit_mode = False
    if 'user_id' in session:
        can_edit_chapter = chapter['author_id'] == session['user_id']
        can_reply_as_author = chapter['author_id'] == session['user_id']
        edit_mode = can_edit_chapter and request.args.get('edit', '') == '1'
        upsert_reading_history(cur, session['user_id'], chapter['story_id'], chapter['chapter_id'])
        conn.commit()

    cur.close()
    conn.close()

    return render_template(
        'chapter.html',
        chapter=chapter,
        prev_chapter_id=prev_row['chapter_id'] if prev_row else None,
        next_chapter_id=next_row['chapter_id'] if next_row else None,
        can_edit_chapter=can_edit_chapter,
        can_reply_as_author=can_reply_as_author,
        edit_mode=edit_mode,
        reading_font_size=reading_font_size,
        reading_line_height=reading_line_height,
        now_utc=datetime.utcnow(),
        comments=root_comments
    )


@app.route('/user/<string:username>')
def user_profile(username):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('''
        SELECT user_id, username, created_at, bio, avatar_url, is_blocked
        FROM users
        WHERE username = %s
    ''', (username,))
    profile = cur.fetchone()

    if not profile or profile['is_blocked']:
        flash('User not found.', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('home'))

    cur.execute('''
        SELECT
            s.story_id,
            s.title,
            s.cover_image,
            s.view_count,
            g.genre_name,
            COALESCE(cs.chapter_count, 0) AS chapter_count,
            COALESCE(fs.follower_count, 0) AS follower_count,
            ROUND(COALESCE(rs.avg_rating, 0), 2) AS avg_rating
        FROM stories s
        JOIN genres g ON s.genre_id = g.genre_id
        LEFT JOIN (
            SELECT story_id, COUNT(*) AS chapter_count
            FROM chapters
            WHERE status = 'published'
              AND published_at <= CURRENT_TIMESTAMP
            GROUP BY story_id
        ) cs ON s.story_id = cs.story_id
        LEFT JOIN (
            SELECT story_id, COUNT(*) AS follower_count
            FROM story_follows
            GROUP BY story_id
        ) fs ON s.story_id = fs.story_id
        LEFT JOIN (
            SELECT story_id, AVG(rating)::numeric AS avg_rating
            FROM ratings
            GROUP BY story_id
        ) rs ON s.story_id = rs.story_id
        WHERE s.author_id = %s AND s.is_published = TRUE
        ORDER BY COALESCE(s.published_at, s.created_at) DESC, s.story_id DESC
    ''', (profile['user_id'],))
    stories = cur.fetchall()

    cur.execute('''
        SELECT COALESCE(COUNT(sf.user_id), 0) AS story_followers
        FROM stories s
        LEFT JOIN story_follows sf ON sf.story_id = s.story_id
        WHERE s.author_id = %s AND s.is_published = TRUE
    ''', (profile['user_id'],))
    story_followers = cur.fetchone()['story_followers']

    cur.execute("SELECT to_regclass('public.user_follows') IS NOT NULL AS exists")
    user_follows_exists = cur.fetchone()['exists']

    user_followers = 0
    if user_follows_exists:
        cur.execute('''
            SELECT COALESCE(COUNT(*), 0) AS user_followers
            FROM user_follows
            WHERE followed_user_id = %s
        ''', (profile['user_id'],))
        user_followers = cur.fetchone()['user_followers']

    total_followers = story_followers + user_followers

    cur.close()
    conn.close()

    return render_template(
        'user_profile.html',
        profile=profile,
        stories=stories,
        story_followers=story_followers,
        user_followers=user_followers,
        total_followers=total_followers
    )


@app.route('/story/<int:story_id>/rate', methods=['POST'])
@login_required
def rate_story(story_id):
    try:
        rating = int(request.form['rating'])
    except (TypeError, ValueError):
        flash('Invalid rating value.', 'error')
        return redirect(url_for('view_story', story_id=story_id))

    if rating < 1 or rating > 5:
        flash('Rating must be between 1 and 5 stars.', 'error')
        return redirect(url_for('view_story', story_id=story_id))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO ratings (story_id, user_id, rating)
            VALUES (%s, %s, %s)
            ON CONFLICT (story_id, user_id)
            DO UPDATE SET rating = EXCLUDED.rating
        ''', (story_id, session['user_id'], rating))
        conn.commit()
        flash('Rating submitted successfully!', 'success')
    except psycopg2.Error:
        conn.rollback()
        flash('Failed to submit rating.', 'error')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('view_story', story_id=story_id))


@app.route('/story/<int:story_id>/review', methods=['POST'])
@login_required
def submit_story_review(story_id):
    title = request.form.get('title', '').strip()
    body = request.form.get('body', '').strip()

    try:
        rating = int(request.form.get('rating', '0'))
    except (TypeError, ValueError):
        flash('Invalid review rating.', 'error')
        return redirect(url_for('view_story', story_id=story_id))

    if rating < 1 or rating > 5:
        flash('Review rating must be between 1 and 5.', 'error')
        return redirect(url_for('view_story', story_id=story_id))

    if not title or not body:
        flash('Review title and body are required.', 'error')
        return redirect(url_for('view_story', story_id=story_id))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            'SELECT author_id, title, is_published FROM stories WHERE story_id = %s',
            (story_id,)
        )
        story = cur.fetchone()

        if not story or not story['is_published']:
            flash('Story not found.', 'error')
            return redirect(url_for('home'))

        if story['author_id'] == session['user_id']:
            flash('You cannot review your own story.', 'error')
            return redirect(url_for('view_story', story_id=story_id))

        # One review per user per story; author can update their own review.
        cur.execute('''
            INSERT INTO story_reviews (story_id, user_id, title, body, rating)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (story_id, user_id)
            DO UPDATE SET
                title = EXCLUDED.title,
                body = EXCLUDED.body,
                rating = EXCLUDED.rating,
                updated_at = CURRENT_TIMESTAMP
        ''', (story_id, session['user_id'], title, body, rating))

        # Keep aggregate rating behavior consistent with existing rating-based stats.
        cur.execute('''
            INSERT INTO ratings (story_id, user_id, rating)
            VALUES (%s, %s, %s)
            ON CONFLICT (story_id, user_id)
            DO UPDATE SET rating = EXCLUDED.rating
        ''', (story_id, session['user_id'], rating))

        create_notification(
            cur,
            story['author_id'],
            f"{session['username']} reviewed your story \"{story['title']}\"."
        )

        conn.commit()
        flash('Review submitted.', 'success')
    except psycopg2.Error:
        conn.rollback()
        flash('Failed to submit review.', 'error')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('view_story', story_id=story_id))


@app.route('/chapter/<int:chapter_id>/comment', methods=['POST'])
@login_required
def comment_on_chapter(chapter_id):
    content = request.form.get('content', '').strip()
    if not content:
        flash('Comment content cannot be empty.', 'error')
        return redirect(request.referrer or url_for('home'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute('''
            SELECT c.story_id, c.status, c.published_at, s.author_id, s.is_published
            FROM chapters c
            JOIN stories s ON c.story_id = s.story_id
            WHERE c.chapter_id = %s
        ''', (chapter_id,))
        chapter = cur.fetchone()
        if not chapter:
            flash('Chapter not found.', 'error')
            return redirect(url_for('home'))
        is_author_view = chapter['author_id'] == session['user_id']
        chapter_is_public = (
            chapter['is_published']
            and chapter['status'] == 'published'
            and chapter['published_at'] is not None
            and chapter['published_at'] <= datetime.utcnow()
        )
        if not is_author_view and not chapter_is_public:
            abort(404)

        cur.execute('''
            INSERT INTO chapter_comments (chapter_id, story_id, user_id, content)
            VALUES (%s, %s, %s, %s)
        ''', (chapter_id, chapter['story_id'], session['user_id'], content))
        conn.commit()
        flash('Comment posted.', 'success')
        return redirect(url_for('view_chapter', chapter_id=chapter_id))
    except psycopg2.Error:
        conn.rollback()
        flash('Failed to post comment.', 'error')
        return redirect(request.referrer or url_for('home'))
    finally:
        cur.close()
        conn.close()


@app.route('/chapter/<int:chapter_id>/comment/<int:comment_id>/reply', methods=['POST'])
@login_required
def reply_to_chapter_comment(chapter_id, comment_id):
    content = request.form.get('content', '').strip()
    if not content:
        flash('Reply content cannot be empty.', 'error')
        return redirect(request.referrer or url_for('home'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute('''
            SELECT c.story_id, c.status, c.published_at, s.author_id, s.title, s.is_published
            FROM chapters c
            JOIN stories s ON c.story_id = s.story_id
            WHERE c.chapter_id = %s
        ''', (chapter_id,))
        chapter_story = cur.fetchone()

        if not chapter_story:
            flash('Chapter not found.', 'error')
            return redirect(url_for('home'))

        chapter_is_public = (
            chapter_story['is_published']
            and chapter_story['status'] == 'published'
            and chapter_story['published_at'] is not None
            and chapter_story['published_at'] <= datetime.utcnow()
        )
        if chapter_story['author_id'] != session['user_id'] and not chapter_is_public:
            abort(404)

        if chapter_story['author_id'] != session['user_id']:
            flash('Only the story author can post replies here.', 'error')
            return redirect(url_for('view_chapter', chapter_id=chapter_id))

        cur.execute('''
            SELECT user_id
            FROM chapter_comments
            WHERE comment_id = %s AND chapter_id = %s
        ''', (comment_id, chapter_id))
        target_comment = cur.fetchone()

        if not target_comment:
            flash('Comment not found.', 'error')
            return redirect(url_for('view_chapter', chapter_id=chapter_id))

        cur.execute('''
            INSERT INTO chapter_comments (chapter_id, story_id, user_id, parent_comment_id, content)
            VALUES (%s, %s, %s, %s, %s)
        ''', (chapter_id, chapter_story['story_id'], session['user_id'], comment_id, content))

        if target_comment['user_id'] != session['user_id']:
            create_notification(
                cur,
                target_comment['user_id'],
                f"{session['username']} replied to your comment on \"{chapter_story['title']}\"."
            )

        conn.commit()
        flash('Reply posted.', 'success')
        return redirect(url_for('view_chapter', chapter_id=chapter_id))
    except psycopg2.Error:
        conn.rollback()
        flash('Failed to post reply.', 'error')
        return redirect(request.referrer or url_for('home'))
    finally:
        cur.close()
        conn.close()


@app.route('/story/<int:story_id>/follow', methods=['POST'])
@login_required
def follow_story(story_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO story_follows (story_id, user_id)
            VALUES (%s, %s)
            ON CONFLICT (story_id, user_id) DO NOTHING
        ''', (story_id, session['user_id']))
        conn.commit()
        flash('Story followed.', 'success')
    except psycopg2.Error:
        conn.rollback()
        flash('Failed to follow story.', 'error')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('view_story', story_id=story_id))


@app.route('/story/<int:story_id>/unfollow', methods=['POST'])
@login_required
def unfollow_story(story_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            'DELETE FROM story_follows WHERE story_id = %s AND user_id = %s',
            (story_id, session['user_id'])
        )
        conn.commit()
        flash('Story unfollowed.', 'success')
    except psycopg2.Error:
        conn.rollback()
        flash('Failed to unfollow story.', 'error')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('view_story', story_id=story_id))


@app.route('/reading-list')
@login_required
def reading_list_page():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT
            s.story_id,
            s.title,
            s.cover_image,
            s.view_count,
            u.username AS author_name,
            g.genre_name,
            ROUND(COALESCE(AVG(r.rating), 0), 2) AS avg_rating,
            MAX(sf.created_at) AS followed_at
        FROM story_follows sf
        JOIN stories s ON sf.story_id = s.story_id
        JOIN users u ON s.author_id = u.user_id
        JOIN genres g ON s.genre_id = g.genre_id
        LEFT JOIN ratings r ON s.story_id = r.story_id
        WHERE sf.user_id = %s
          AND s.is_published = TRUE
        GROUP BY s.story_id, u.username, g.genre_name
        ORDER BY followed_at DESC
    ''', (session['user_id'],))
    stories = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('reading_list.html', stories=stories)


@app.route('/author/dashboard')
@login_required
def author_dashboard():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('''
        SELECT
            s.*,
            g.genre_name,
            COALESCE(cs.chapter_count, 0) AS chapter_count,
            COALESCE(fs.follower_count, 0) AS follower_count,
            ROUND(COALESCE(rs.avg_rating, 0), 2) AS avg_rating
        FROM stories s
        JOIN genres g ON s.genre_id = g.genre_id
        LEFT JOIN (
            SELECT story_id, COUNT(*) AS chapter_count
            FROM chapters
            GROUP BY story_id
        ) cs ON s.story_id = cs.story_id
        LEFT JOIN (
            SELECT story_id, COUNT(*) AS follower_count
            FROM story_follows
            GROUP BY story_id
        ) fs ON s.story_id = fs.story_id
        LEFT JOIN (
            SELECT story_id, AVG(rating)::numeric AS avg_rating
            FROM ratings
            GROUP BY story_id
        ) rs ON s.story_id = rs.story_id
        WHERE s.author_id = %s
        ORDER BY s.created_at DESC
    ''', (session['user_id'],))
    stories = cur.fetchall()

    cur.execute('''
        SELECT *
        FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 10
    ''', (session['user_id'],))
    notifications = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'author_dashboard.html',
        stories=stories,
        notifications=notifications,
        sidebar_stories=stories
    )


@app.route('/author/story/select', methods=['POST'])
@login_required
def select_story_for_chapters():
    story_id = request.form.get('story_id', type=int)
    if not story_id:
        flash('Please select a story first.', 'error')
        return redirect(url_for('author_dashboard'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        'SELECT story_id FROM stories WHERE story_id = %s AND author_id = %s',
        (story_id, session['user_id'])
    )
    story = cur.fetchone()
    cur.close()
    conn.close()

    if not story:
        flash('Story not found or unauthorized.', 'error')
        return redirect(url_for('author_dashboard'))

    return redirect(url_for('edit_story', story_id=story_id))


@app.route('/author/analytics')
@login_required
def author_analytics():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('SELECT COUNT(*) AS total_stories, COALESCE(SUM(view_count), 0) AS total_views FROM stories WHERE author_id = %s', (session['user_id'],))
    metrics_row = cur.fetchone()

    cur.execute('''
        SELECT COALESCE(COUNT(sf.user_id), 0) AS total_followers
        FROM stories s
        LEFT JOIN story_follows sf ON sf.story_id = s.story_id
        WHERE s.author_id = %s
    ''', (session['user_id'],))
    followers_row = cur.fetchone()

    cur.execute('''
        SELECT ROUND(COALESCE(AVG(story_avg.avg_rating), 0), 2) AS avg_rating
        FROM (
            SELECT s.story_id, AVG(r.rating)::numeric AS avg_rating
            FROM stories s
            LEFT JOIN ratings r ON r.story_id = s.story_id
            WHERE s.author_id = %s
            GROUP BY s.story_id
        ) story_avg
    ''', (session['user_id'],))
    avg_row = cur.fetchone()

    cur.execute('''
        SELECT title, view_count
        FROM stories
        WHERE author_id = %s
        ORDER BY view_count DESC, story_id DESC
        LIMIT 8
    ''', (session['user_id'],))
    chart_rows = cur.fetchall()

    cur.execute('''
        SELECT
            sr.title,
            sr.body AS comment,
            sr.rating,
            u.username,
            sr.created_at
        FROM story_reviews sr
        JOIN stories s ON sr.story_id = s.story_id
        JOIN users u ON sr.user_id = u.user_id
        WHERE s.author_id = %s
        ORDER BY sr.created_at DESC
        LIMIT 8
    ''', (session['user_id'],))
    recent_reviews = cur.fetchall()

    cur.execute('''
        SELECT
            s.story_id,
            s.title,
            s.cover_image,
            s.view_count,
            ROUND(COALESCE(AVG(r.rating), 0), 2) AS avg_rating
        FROM stories s
        LEFT JOIN ratings r ON r.story_id = s.story_id
        WHERE s.author_id = %s
        GROUP BY s.story_id
        ORDER BY s.view_count DESC, avg_rating DESC, s.story_id DESC
        LIMIT 10
    ''', (session['user_id'],))
    top_stories = cur.fetchall()

    cur.execute('''
        SELECT story_id, title
        FROM stories
        WHERE author_id = %s
        ORDER BY created_at DESC
    ''', (session['user_id'],))
    sidebar_stories = cur.fetchall()

    cur.close()
    conn.close()

    metrics = {
        'total_stories': metrics_row['total_stories'],
        'total_views': metrics_row['total_views'],
        'total_followers': followers_row['total_followers'],
        'avg_rating': avg_row['avg_rating']
    }

    chart_labels = [row['title'] for row in chart_rows]
    chart_values = [row['view_count'] for row in chart_rows]

    return render_template(
        'author_analytics.html',
        metrics=metrics,
        chart_labels=chart_labels,
        chart_values=chart_values,
        recent_reviews=recent_reviews,
        top_stories=top_stories,
        sidebar_stories=sidebar_stories
    )


@app.route('/notifications')
@login_required
def notifications_page():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT notification_id, message, is_read, created_at
        FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
    ''', (session['user_id'],))
    notifications = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('notifications.html', notifications=notifications)


@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE notifications
            SET is_read = TRUE
            WHERE user_id = %s AND is_read = FALSE
        ''', (session['user_id'],))
        conn.commit()
        flash('All notifications marked as read.', 'success')
    except psycopg2.Error:
        conn.rollback()
        flash('Failed to update notifications.', 'error')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('notifications_page'))


@app.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE notifications
            SET is_read = TRUE
            WHERE notification_id = %s AND user_id = %s
        ''', (notification_id, session['user_id']))
        conn.commit()
    except psycopg2.Error:
        conn.rollback()
        flash('Failed to update notification.', 'error')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('notifications_page'))


@app.route('/author/create', methods=['GET', 'POST'])
@login_required
def create_story():
    if request.method == 'POST':
        title = request.form['title'].strip()
        description = request.form['description'].strip()
        genre_id = request.form['genre_id']
        cover_file = request.files.get('cover_image')
        cover_image_url = request.form.get('cover_image_url', '').strip()
        cover_path = None

        if cover_file and cover_file.filename:
            cover_path = save_cover_image(cover_file)
        elif cover_image_url:
            if not is_valid_cover_url(cover_image_url):
                flash('Invalid cover URL. Use a direct image URL ending in png/jpg/jpeg/webp/gif.', 'error')
                return redirect(url_for('create_story'))
            cover_path = cover_image_url

        if cover_file and cover_file.filename and not cover_path:
            flash('Invalid cover image. Use png/jpg/jpeg/webp/gif (max 2MB).', 'error')
            return redirect(url_for('create_story'))

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('''
                INSERT INTO stories (title, description, author_id, genre_id, cover_image)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING story_id
            ''', (title, description, session['user_id'], genre_id, cover_path))
            story_id = cur.fetchone()[0]

            # First story creation upgrades account behaviorally into an author.
            cur.execute('UPDATE users SET is_author = TRUE WHERE user_id = %s', (session['user_id'],))
            conn.commit()
            session['is_author'] = True

            flash('Story created successfully!', 'success')
            return redirect(url_for('edit_story', story_id=story_id))
        except psycopg2.Error:
            conn.rollback()
            flash('Failed to create story.', 'error')
        finally:
            cur.close()
            conn.close()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM genres ORDER BY genre_name')
    genres = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('create_story.html', genres=genres)


@app.route('/author/story/<int:story_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_story(story_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        'SELECT * FROM stories WHERE story_id = %s AND author_id = %s',
        (story_id, session['user_id'])
    )
    story = cur.fetchone()

    if not story:
        flash('Story not found or unauthorized.', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('author_dashboard'))

    cur.execute(
        'SELECT * FROM chapters WHERE story_id = %s ORDER BY chapter_number',
        (story_id,)
    )
    chapters = cur.fetchall()

    cur.execute('SELECT * FROM genres ORDER BY genre_name')
    genres = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'edit_story.html',
        story=story,
        chapters=chapters,
        genres=genres,
        now_utc=datetime.utcnow()
    )


@app.route('/author/chapter/<int:chapter_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_chapter(chapter_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('''
        SELECT
            c.chapter_id,
            c.story_id,
            c.chapter_number,
            c.title,
            c.content,
            c.status,
            c.published_at,
            s.author_id
        FROM chapters c
        JOIN stories s ON c.story_id = s.story_id
        WHERE c.chapter_id = %s
    ''', (chapter_id,))
    chapter = cur.fetchone()

    if not chapter or chapter['author_id'] != session['user_id']:
        flash('Unauthorized.', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('author_dashboard'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        action = request.form.get('action', 'draft').strip().lower()
        if action not in ('draft', 'publish_now', 'schedule'):
            action = 'draft'
        schedule_at_raw = request.form.get('schedule_at', '').strip()
        schedule_at = None

        if not title or not content:
            flash('Chapter title and content are required.', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('edit_chapter', chapter_id=chapter_id))

        if action == 'schedule':
            if not schedule_at_raw:
                flash('Schedule datetime is required.', 'error')
                cur.close()
                conn.close()
                return redirect(url_for('edit_chapter', chapter_id=chapter_id))
            try:
                schedule_at = datetime.strptime(schedule_at_raw, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Invalid schedule datetime.', 'error')
                cur.close()
                conn.close()
                return redirect(url_for('edit_chapter', chapter_id=chapter_id))
            if schedule_at <= datetime.utcnow():
                flash('Scheduled time must be in the future.', 'error')
                cur.close()
                conn.close()
                return redirect(url_for('edit_chapter', chapter_id=chapter_id))

        try:
            # Preserve chapter identity/order while supporting scheduled publishing.
            target_status = 'draft'
            target_published_at = None
            if action == 'publish_now':
                target_status = 'published'
                target_published_at = datetime.utcnow()
            elif action == 'schedule':
                target_status = 'published'
                target_published_at = schedule_at

            cur.execute('''
                UPDATE chapters
                SET
                    title = %s,
                    content = %s,
                    status = %s,
                    published_at = %s
                WHERE chapter_id = %s
            ''', (title, content, target_status, target_published_at, chapter_id))
            conn.commit()
            if action == 'draft':
                flash('Chapter saved as draft.', 'success')
            elif action == 'publish_now':
                flash('Chapter published successfully.', 'success')
            else:
                flash(f'Chapter scheduled for {schedule_at.strftime("%Y-%m-%d %H:%M")}.', 'success')
            cur.close()
            conn.close()
            return redirect(url_for('view_chapter', chapter_id=chapter_id))
        except psycopg2.Error:
            conn.rollback()
            flash('Failed to update chapter.', 'error')

    cur.close()
    conn.close()
    return render_template('edit_chapter.html', chapter=chapter, now_utc=datetime.utcnow())


@app.route('/author/story/<int:story_id>/update', methods=['POST'])
@login_required
def update_story(story_id):
    title = request.form['title'].strip()
    description = request.form['description'].strip()
    genre_id = request.form['genre_id']
    cover_file = request.files.get('cover_image')
    cover_image_url = request.form.get('cover_image_url', '').strip()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        'SELECT * FROM stories WHERE story_id = %s AND author_id = %s',
        (story_id, session['user_id'])
    )
    story = cur.fetchone()

    if not story:
        cur.close()
        conn.close()
        flash('Story not found or unauthorized.', 'error')
        return redirect(url_for('author_dashboard'))

    cover_path = story['cover_image']
    if cover_file and cover_file.filename:
        new_cover_path = save_cover_image(cover_file)
        if not new_cover_path:
            cur.close()
            conn.close()
            flash('Invalid cover image. Use png/jpg/jpeg/webp/gif (max 2MB).', 'error')
            return redirect(url_for('edit_story', story_id=story_id))
        cover_path = new_cover_path
    elif cover_image_url:
        if not is_valid_cover_url(cover_image_url):
            cur.close()
            conn.close()
            flash('Invalid cover URL. Use a direct image URL ending in png/jpg/jpeg/webp/gif.', 'error')
            return redirect(url_for('edit_story', story_id=story_id))
        cover_path = cover_image_url

    try:
        cur.execute('''
            UPDATE stories
            SET title = %s, description = %s, genre_id = %s, cover_image = %s
            WHERE story_id = %s AND author_id = %s
        ''', (title, description, genre_id, cover_path, story_id, session['user_id']))
        conn.commit()
        flash('Story updated successfully!', 'success')
    except psycopg2.Error:
        conn.rollback()
        flash('Failed to update story.', 'error')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('edit_story', story_id=story_id))


@app.route('/author/story/<int:story_id>/add-chapter', methods=['POST'])
@login_required
def add_chapter(story_id):
    title = request.form['title'].strip()
    content = request.form['content'].strip()
    action = request.form.get('action', 'draft').strip().lower()
    if action not in ('draft', 'publish_now', 'schedule'):
        action = 'draft'
    schedule_at_raw = request.form.get('schedule_at', '').strip()
    schedule_at = None

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('SELECT author_id, title FROM stories WHERE story_id = %s', (story_id,))
    result = cur.fetchone()
    if not result or result[0] != session['user_id']:
        flash('Unauthorized.', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('author_dashboard'))

    if action == 'schedule':
        if not schedule_at_raw:
            flash('Schedule datetime is required.', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('edit_story', story_id=story_id))
        try:
            schedule_at = datetime.strptime(schedule_at_raw, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid schedule datetime.', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('edit_story', story_id=story_id))
        if schedule_at <= datetime.utcnow():
            flash('Scheduled time must be in the future.', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('edit_story', story_id=story_id))

    try:
        cur.execute(
            'SELECT COALESCE(MAX(chapter_number), 0) + 1 FROM chapters WHERE story_id = %s',
            (story_id,)
        )
        chapter_number = cur.fetchone()[0]

        # Reader visibility is time-gated by published_at.
        target_status = 'draft'
        target_published_at = None
        if action == 'publish_now':
            target_status = 'published'
            target_published_at = datetime.utcnow()
        elif action == 'schedule':
            target_status = 'published'
            target_published_at = schedule_at

        cur.execute('''
            INSERT INTO chapters (story_id, chapter_number, title, content, status, published_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (story_id, chapter_number, title, content, target_status, target_published_at))

        if action == 'publish_now':
            # Notify followers about a newly published chapter in stories they follow.
            cur.execute('''
                INSERT INTO notifications (user_id, message)
                SELECT sf.user_id, %s
                FROM story_follows sf
                WHERE sf.story_id = %s
                  AND sf.user_id <> %s
            ''', (
                f'New chapter ({chapter_number}) in "{result[1]}".',
                story_id,
                session['user_id']
            ))

        conn.commit()
        if action == 'draft':
            flash('Chapter saved as draft.', 'success')
        elif action == 'publish_now':
            flash('Chapter published successfully!', 'success')
        else:
            flash(f'Chapter scheduled for {schedule_at.strftime("%Y-%m-%d %H:%M")}.', 'success')
    except psycopg2.Error:
        conn.rollback()
        flash('Failed to add chapter.', 'error')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('edit_story', story_id=story_id))


@app.route('/author/story/<int:story_id>/publish', methods=['POST'])
@login_required
def publish_story(story_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('SELECT publish_story(%s, %s)', (story_id, session['user_id']))
        conn.commit()
        flash('Story published successfully!', 'success')
    except psycopg2.Error as e:
        conn.rollback()
        flash(f'Failed to publish story: {str(e)}', 'error')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('author_dashboard'))


@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('SELECT COUNT(*) AS total FROM users')
    total_users = cur.fetchone()['total']

    cur.execute('SELECT COUNT(*) AS total FROM stories WHERE is_published = TRUE')
    total_stories = cur.fetchone()['total']

    cur.execute('SELECT COUNT(*) AS total FROM reports WHERE status = %s', ('pending',))
    pending_reports = cur.fetchone()['total']

    cur.execute('''
        SELECT r.*, s.title AS story_title, u.username AS reporter_name
        FROM reports r
        JOIN stories s ON r.story_id = s.story_id
        JOIN users u ON r.reported_by = u.user_id
        WHERE r.status = 'pending'
        ORDER BY r.created_at DESC
    ''')
    reports = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'admin_dashboard.html',
        total_users=total_users,
        total_stories=total_stories,
        pending_reports=pending_reports,
        reports=reports
    )


@app.route('/admin/block-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def block_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('UPDATE users SET is_blocked = TRUE WHERE user_id = %s', (user_id,))
        conn.commit()
        flash('User blocked successfully.', 'success')
    except psycopg2.Error:
        conn.rollback()
        flash('Failed to block user.', 'error')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/remove-story/<int:story_id>', methods=['POST'])
@login_required
@admin_required
def remove_story(story_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM stories WHERE story_id = %s', (story_id,))
        conn.commit()
        flash('Story removed successfully.', 'success')
    except psycopg2.Error:
        conn.rollback()
        flash('Failed to remove story.', 'error')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('admin_dashboard'))


@app.errorhandler(413)
def request_entity_too_large(error):
    flash('Cover image is too large. Maximum size is 2MB.', 'error')
    return redirect(request.referrer or url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)
