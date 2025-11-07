-- This is bascially our database setup run book, it tells the db what tables to create and it runs similar to a one-time-use script

CREATE TABLE users (
    id UUID PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    api_key TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chats (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT now()
    report_id UUID REFERENCES match_analysis_reports(id) ON DELETE SET NULL
);

CREATE TABLE messages (
    id UUID PRIMARY KEY,
    chat_id UUID REFERENCES chats(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    replied_to_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    role TEXT CHECK (role IN ('user','assistant', 'system')) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- create a chat_id -> created_at index to speed up query time, this way if we query for messages in a chat, we can quickly pull them rather than
-- scanning the entire table to accumulate a list of the correct chats. Similar for created_at subindex. 
CREATE INDEX idx_messages_chat_created ON messages(chat_id, created_at);

CREATE TABLE match_analysis_reports (
    id UUID PRIMARY KEY,
    team1 TEXT NOT NULL,
    team2 TEXT NOT NULL,
    game_date DATE NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_reports_teams_date ON match_analysis_reports(team1, team2, game_date);


INSERT INTO users (id, username, api_key) VALUES 
('97428650-14f8-4a83-aeb3-ef79f6929828', 'Will', 'willshannon89@gmail.com'),
('c25d9704-17d5-4d45-b1be-bf321cfcbcce', 'Doug', 'dougshannon@mac.com'),
('ec123804-070c-4bd2-8b05-11bd721e7796', 'Dave', 'dave_blum@hotmail.com');