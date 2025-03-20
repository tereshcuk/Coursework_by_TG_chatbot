import psycopg2
import os


def get_db_connection():
            
    database = os.getenv('database')    
    if database is None:        
        os.environ['database'] = 'user_dictionary'
        database =  os.environ['database']
    
    user = os.getenv('user')
    if user is None:        
        os.environ['user'] = 'postgres'
        user = os.environ['user'] 
       
    password = os.getenv('password')
    if password is None: 
        password = input("Введите пароль для подключения к БД :")       
        os.environ['password'] = password
            
    conn = psycopg2.connect(database=database, user=user, password=password)    
    return conn 

def initialize():    
    initialize_db()
    initialize_data()  

# Функция создает таблицы в базе данных и заполняет их начальными данными
def initialize_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            
            # Создадим таблицу пользователей
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users(
                    user_id SERIAL PRIMARY KEY NOT NULL UNIQUE,
                    user_name VARCHAR(150) NOT NULL
            );
            """)
            # Создадим таблицу слов
            cur.execute("""
                CREATE TABLE IF NOT EXISTS words(
                    word_id SERIAL PRIMARY KEY NOT NULL UNIQUE,
                    word_in_english VARCHAR(150) NOT NULL,
                    word_in_russian VARCHAR(150) NOT NULL, 
                    CONSTRAINT words_unique UNIQUE (word_in_english, word_in_russian));
            """)          
            
            # Создадим таблицу cловарь пользователей
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users_words(
                    id SERIAL PRIMARY KEY NOT NULL UNIQUE,
                    user_id INTEGER REFERENCES users(user_id),
                    word_id INTEGER REFERENCES words(word_id),
                   CONSTRAINT users_words_unique UNIQUE (user_id, word_id));
            """)
            
def initialize_data():                        
    # Запоним первоначальными словами таблицу words
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) from words");
            count = cur.fetchone()[0]            
            if count == 0:
                words = [('Peace', 'Мир'), ('Green', 'Зелёный'), ('White', 'Белый'),
                     ('Hello', 'Привет'), ('Car', 'Машина'), ('Sky', 'Небо'),
                     ('Tree', 'Дерево'), ('Book', 'Книга'), ('Love', 'Любовь'),
                     ('Friend', 'Друг')                ]
                fill_words(words)
                
           
            
            
# Функция заполняет таблицу со словами
def fill_words(set_of_words):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for i in set_of_words:
                cur.execute("""
                INSERT into words(word_in_english, word_in_russian)
                VALUES (%s, %s)
                ;""", i)


# Функция получает случайные слова
def get_random_words(user_id, limit=3, exclude=''):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            text_sql = """   
               select w.word_in_english, w.word_in_russian
                    from users_words uw                   
                      inner join words as w on uw.word_id = w.word_id
                    where uw.user_id = %s  
                          and w.word_in_english <> %s
                order by RANDOM()
                limit %s
            """
            cur.execute(text_sql, (user_id, exclude, limit))
            result = cur.fetchall()
    return result



# Функция проверяет, существует ли пользователь в базе данных и создает его, если необходимо
def check_user(user_id, user_name):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                    INSERT INTO users (user_id, user_name)
                    VALUES (%s, %s)
                      ON CONFLICT (user_id) DO UPDATE SET 
                      user_id = EXCLUDED.user_id, user_name = EXCLUDED.user_name;
                    """, (user_id, user_name))
    add_words_for_new_user(user_id)        
            

# Функция заполняет словарь для пользователя 
def add_words_for_new_user(user_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select word_id from words w;")
            all_words = cur.fetchall()
            for word in all_words:
                cur.execute("""
                        INSERT INTO users_words
                            (user_id, word_id)
                        VALUES(%s, %s)
                        ON CONFLICT (user_id, word_id) DO NOTHING;                      
            
            """, (user_id, word[0]))            
            
# Функция получает всех пользователей 
def get_all_user():
    users =[]
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id
                FROM users;
                """)
            result= cur.fetchall()
    for str in result:
        users.append(str[0])
        
    return users    
             

# Функция проверяет, существует ли слово
def check_word_existence(word):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT word_id
            FROM words
            WHERE word_in_english = %s;
            """, (word,))
            return cur.fetchone() is not None


# Сохраняет слово в словарь
def add_word_to_user(user_id, target_word, translate_word):
    id_word = None
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO words (word_in_english, word_in_russian)
                    VALUES (%s, %s)
                  ON CONFLICT (word_in_english, word_in_russian) DO NOTHING
                RETURNING word_id;
            """, (target_word.strip().capitalize(), translate_word.strip().capitalize()))
            id_word = cur.fetchone()
            
    if not id_word is None:                
        update_word_to_user_dict(user_id, target_word, translate_word)
    else:
        conn.rollback
    return id_word[0]

#  Функция удаляет слово из персонального словаря
def delete_user_word(user_id, word_to_delete_r):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM users_words
                WHERE user_id = %s
                AND word_id = (select word_id from words where word_in_russian =  %s)
                RETURNING id;
            """, (user_id, word_to_delete_r))
            result = cur.fetchone()
    return result         


# Обновляет персональный словарь.
def update_word_to_user_dict(user_id, target_word, translate_word):
    with get_db_connection() as conn:
        with conn.cursor() as cur:            
            cur.execute("""
                        INSERT INTO users_words (user_id, word_id)
                        VALUES (%s, (select word_id from words where word_in_english = %s and word_in_russian = %s))  
                        ON CONFLICT (user_id, word_id) DO NOTHING          
            """, (user_id, target_word, translate_word,))
            
    

if __name__ == '__main__':
    
    initialize()
    check_user(1, '111')
    add_word_to_user(1, 'target_word', 'translate_word')

