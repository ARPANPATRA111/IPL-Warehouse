INSERT INTO dim_dismissal_type (dismissal_type, is_bowler_credited, is_fielder_involved, description) VALUES
('bowled', TRUE, FALSE, 'Bowler hits the stumps'),
('caught', TRUE, TRUE, 'Batsman caught by fielder'),
('caught and bowled', TRUE, FALSE, 'Caught by the bowler'),
('lbw', TRUE, FALSE, 'Leg before wicket'),
('stumped', TRUE, TRUE, 'Wicketkeeper disturbs stumps'),
('run out', FALSE, TRUE, 'Batsman run out'),
('hit wicket', TRUE, FALSE, 'Batsman hits own stumps'),
('retired hurt', FALSE, FALSE, 'Batsman retires due to injury'),
('retired out', FALSE, FALSE, 'Batsman retires voluntarily'),
('obstructing the field', FALSE, FALSE, 'Batsman obstructs fielding'),
('handled the ball', FALSE, FALSE, 'Batsman handles ball illegally'),
('timed out', FALSE, FALSE, 'Incoming batsman timed out')
ON CONFLICT (dismissal_type) DO NOTHING;

INSERT INTO dim_extras_type (extras_type, is_charged_to_bowler, is_legal_delivery) VALUES
('wides', TRUE, FALSE),
('noballs', TRUE, FALSE),
('byes', FALSE, TRUE),
('legbyes', FALSE, TRUE),
('penalty', FALSE, TRUE)
ON CONFLICT (extras_type) DO NOTHING;
