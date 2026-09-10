"""
F1 Quiz Bot - Question Bank
Each question is a dict:
{
    "question": str,          # poll question text (Telegram limit ~255 chars)
    "options": [str, ...],    # 2-10 options (Telegram limit ~100 chars each)
    "correct": int,           # index into options
    "explanation": str,       # shown after answering (Telegram limit ~200 chars)
    "category": str,          # "history" | "records" | "drivers" | "teams" | "meme" | "rules"
    "difficulty": str,        # "easy" | "medium" | "hard" -> controls points awarded
}

NOTE: F1 stats (records, current champions, team names) change every season.
This bank is accurate through the 2023-2024 seasons. Revisit periodically —
see the bottom of this file for how to add more questions.
"""

QUESTIONS = [
    # ---------------- HISTORY ----------------
    {
        "question": "Who won the very first Formula 1 World Championship (1950)?",
        "options": ["Juan Manuel Fangio", "Giuseppe Farina", "Alberto Ascari", "Stirling Moss"],
        "correct": 1,
        "explanation": "Giuseppe 'Nino' Farina won the inaugural 1950 title driving for Alfa Romeo.",
        "category": "history",
        "difficulty": "hard",
    },
    {
        "question": "Which driver has won the most F1 World Championships (7, alongside one other)?",
        "options": ["Ayrton Senna", "Alain Prost", "Michael Schumacher", "Niki Lauda"],
        "correct": 2,
        "explanation": "Michael Schumacher and Lewis Hamilton are tied with 7 titles each.",
        "category": "history",
        "difficulty": "easy",
    },
    {
        "question": "In which decade did the first Monaco Grand Prix (as part of the F1 championship) take place?",
        "options": ["1920s", "1930s", "1950s", "1960s"],
        "correct": 2,
        "explanation": "Monaco joined the F1 calendar in 1950, the championship's very first year.",
        "category": "history",
        "difficulty": "medium",
    },
    {
        "question": "Which team did Ayrton Senna famously drive for when he won his 3 world titles?",
        "options": ["Williams", "Ferrari", "McLaren", "Lotus"],
        "correct": 2,
        "explanation": "Senna won his titles (1988, 1990, 1991) with McLaren-Honda.",
        "category": "history",
        "difficulty": "easy",
    },
    {
        "question": "Who is the youngest World Champion in F1 history (as of 2024)?",
        "options": ["Max Verstappen", "Lewis Hamilton", "Sebastian Vettel", "Fernando Alonso"],
        "correct": 2,
        "explanation": "Sebastian Vettel won his first title in 2010 at 23 years old.",
        "category": "history",
        "difficulty": "medium",
    },
    {
        "question": "Which nation has produced the most F1 World Champions?",
        "options": ["Germany", "Brazil", "United Kingdom", "Italy"],
        "correct": 2,
        "explanation": "The UK leads with champions like Hamilton, Hill, Mansell, Stewart and more.",
        "category": "history",
        "difficulty": "medium",
    },
    {
        "question": "What year did Formula 1 introduce the current V6 turbo-hybrid power units?",
        "options": ["2010", "2012", "2014", "2017"],
        "correct": 2,
        "explanation": "The 1.6L V6 turbo-hybrid era began in the 2014 season.",
        "category": "history",
        "difficulty": "medium",
    },
    {
        "question": "Which driver won the closest-ever title fight, decided by just half a point in 1984?",
        "options": ["Niki Lauda", "Alain Prost", "Nelson Piquet", "Keke Rosberg"],
        "correct": 0,
        "explanation": "Niki Lauda beat teammate Alain Prost by half a point — the closest title margin ever.",
        "category": "history",
        "difficulty": "hard",
    },
    {
        "question": "Who was the first driver to win a Formula 1 World Championship for Ferrari?",
        "options": ["Juan Manuel Fangio", "Alberto Ascari", "Mike Hawthorn", "Phil Hill"],
        "correct": 1,
        "explanation": "Alberto Ascari won Ferrari's first drivers' titles in 1952 and 1953.",
        "category": "history",
        "difficulty": "hard",
    },
    {
        "question": "Which race has most often closed out the F1 season in recent years?",
        "options": ["Abu Dhabi GP", "Brazilian GP", "Japanese GP", "United States GP"],
        "correct": 0,
        "explanation": "The Abu Dhabi Grand Prix at Yas Marina has closed the calendar in most recent seasons.",
        "category": "history",
        "difficulty": "easy",
    },

    # ---------------- RECORDS ----------------
    {
        "question": "Who holds the record for most F1 race wins in history (as of 2024)?",
        "options": ["Michael Schumacher", "Lewis Hamilton", "Sebastian Vettel", "Max Verstappen"],
        "correct": 1,
        "explanation": "Lewis Hamilton passed Schumacher's tally and leads the all-time wins list.",
        "category": "records",
        "difficulty": "easy",
    },
    {
        "question": "Who holds the record for most pole positions in F1 history?",
        "options": ["Ayrton Senna", "Michael Schumacher", "Lewis Hamilton", "Max Verstappen"],
        "correct": 2,
        "explanation": "Lewis Hamilton holds the all-time pole record, surpassing Senna and Schumacher.",
        "category": "records",
        "difficulty": "medium",
    },
    {
        "question": "Which team has won the most Constructors' Championships?",
        "options": ["McLaren", "Williams", "Ferrari", "Mercedes"],
        "correct": 2,
        "explanation": "Ferrari leads all teams in Constructors' titles by a wide margin.",
        "category": "records",
        "difficulty": "easy",
    },
    {
        "question": "In 2023, which driver set the record for most consecutive race wins in a single season?",
        "options": ["Lewis Hamilton", "Sebastian Vettel", "Max Verstappen", "Michael Schumacher"],
        "correct": 2,
        "explanation": "Max Verstappen won 10 consecutive races in 2023, a new F1 record.",
        "category": "records",
        "difficulty": "easy",
    },
    {
        "question": "Which team won a record 21 of 22 races in the 2023 season?",
        "options": ["McLaren", "Mercedes", "Ferrari", "Red Bull Racing"],
        "correct": 3,
        "explanation": "Red Bull's 2023 campaign is the most dominant single-team season in F1 history.",
        "category": "records",
        "difficulty": "medium",
    },
    {
        "question": "Who is the oldest driver to win an F1 World Championship?",
        "options": ["Juan Manuel Fangio", "Nigel Mansell", "Alain Prost", "Niki Lauda"],
        "correct": 0,
        "explanation": "Fangio won his fifth title in 1957 at age 46, the oldest champion ever.",
        "category": "records",
        "difficulty": "hard",
    },
    {
        "question": "Which circuit has hosted the most F1 World Championship races?",
        "options": ["Silverstone", "Monza", "Monaco", "Spa-Francorchamps"],
        "correct": 1,
        "explanation": "Monza has hosted an F1 race in almost every season since 1950, the most of any circuit.",
        "category": "records",
        "difficulty": "hard",
    },

    # ---------------- DRIVERS ----------------
    {
        "question": "Which driver's nickname is 'The Iceman'?",
        "options": ["Sebastian Vettel", "Kimi Raikkonen", "Valtteri Bottas", "Nico Rosberg"],
        "correct": 1,
        "explanation": "Kimi Raikkonen earned 'The Iceman' tag for his cool, deadpan demeanor.",
        "category": "drivers",
        "difficulty": "easy",
    },
    {
        "question": "Which driver is the son of a former F1 driver and dominated the sport in the early 2020s?",
        "options": ["Lando Norris", "Max Verstappen", "Charles Leclerc", "George Russell"],
        "correct": 1,
        "explanation": "Max Verstappen, son of ex-F1 driver Jos Verstappen, dominated 2021-2023.",
        "category": "drivers",
        "difficulty": "easy",
    },
    {
        "question": "Which driver drove for Renault, McLaren, Ferrari, and Alpine across his long F1 career?",
        "options": ["Jenson Button", "Fernando Alonso", "Felipe Massa", "Mark Webber"],
        "correct": 1,
        "explanation": "Fernando Alonso has raced for many teams including Renault, McLaren, Ferrari and Alpine.",
        "category": "drivers",
        "difficulty": "medium",
    },
    {
        "question": "Who was on the receiving end of the 'Multi-21' team orders controversy with Sebastian Vettel in 2013?",
        "options": ["Daniel Ricciardo", "Mark Webber", "Rubens Barrichello", "David Coulthard"],
        "correct": 1,
        "explanation": "Vettel ignored a 'Multi-21' hold-position order and passed teammate Mark Webber in Malaysia 2013.",
        "category": "drivers",
        "difficulty": "hard",
    },
    {
        "question": "Which driver is nicknamed the 'Honey Badger'?",
        "options": ["Daniel Ricciardo", "Pierre Gasly", "Carlos Sainz", "Esteban Ocon"],
        "correct": 0,
        "explanation": "Daniel Ricciardo picked up 'Honey Badger' for his fearless driving style.",
        "category": "drivers",
        "difficulty": "medium",
    },
    {
        "question": "Who won the 2021 F1 title on the final lap of the final race in Abu Dhabi amid huge controversy?",
        "options": ["Lewis Hamilton", "Max Verstappen", "Valtteri Bottas", "Sergio Perez"],
        "correct": 1,
        "explanation": "Max Verstappen passed Hamilton on the last lap after a controversial late Safety Car restart.",
        "category": "drivers",
        "difficulty": "easy",
    },
    {
        "question": "Which F1 driver is the son of a Formula 1 legend and raced for Haas in the early 2020s?",
        "options": ["Mick Schumacher", "Nico Hulkenberg", "Kevin Magnussen", "Esteban Ocon"],
        "correct": 0,
        "explanation": "Mick Schumacher, son of Michael Schumacher, raced in F1 for Haas.",
        "category": "drivers",
        "difficulty": "medium",
    },

    # ---------------- TEAMS ----------------
    {
        "question": "Which team is based in Brackley, UK and dominated the hybrid era from 2014-2020?",
        "options": ["Red Bull Racing", "Mercedes-AMG Petronas", "Aston Martin", "Williams"],
        "correct": 1,
        "explanation": "Mercedes is headquartered in Brackley and won 8 straight Constructors' titles from 2014.",
        "category": "teams",
        "difficulty": "medium",
    },
    {
        "question": "Which energy-drink-backed team won 4 straight titles with Vettel (2010-13) and again from 2021?",
        "options": ["Red Bull Racing", "Renault", "Force India", "Toro Rosso"],
        "correct": 0,
        "explanation": "Red Bull Racing has been one of F1's most dominant forces across two separate eras.",
        "category": "teams",
        "difficulty": "easy",
    },
    {
        "question": "What is the oldest continuously competing team in F1?",
        "options": ["McLaren", "Williams", "Ferrari", "Alfa Romeo"],
        "correct": 2,
        "explanation": "Ferrari has competed in every F1 season since the championship began in 1950.",
        "category": "teams",
        "difficulty": "easy",
    },
    {
        "question": "Which team famously raced a 'six-wheeled' car (the P34) in the 1970s?",
        "options": ["Lotus", "Tyrrell", "Brabham", "March"],
        "correct": 1,
        "explanation": "The Tyrrell P34 ran with four small front wheels and even won a race in 1976.",
        "category": "teams",
        "difficulty": "hard",
    },
    {
        "question": "Which team's clever 'double diffuser' helped them dominate the start of the 2009 season?",
        "options": ["Red Bull", "McLaren", "Brawn GP", "Toyota"],
        "correct": 2,
        "explanation": "Brawn GP won both titles in their only F1 season, 2009, thanks in part to the double diffuser.",
        "category": "teams",
        "difficulty": "medium",
    },

    # ---------------- RULES / TECH ----------------
    {
        "question": "How many points does a driver get for winning a Grand Prix under the current system?",
        "options": ["20", "25", "30", "10"],
        "correct": 1,
        "explanation": "A race win is worth 25 points under the scoring system introduced in 2010.",
        "category": "rules",
        "difficulty": "easy",
    },
    {
        "question": "What is DRS in Formula 1?",
        "options": [
            "Drag Reduction System",
            "Downforce Regulation Standard",
            "Driver Radio System",
            "Dynamic Race Strategy",
        ],
        "correct": 0,
        "explanation": "DRS opens a flap on the rear wing to reduce drag and aid overtaking.",
        "category": "rules",
        "difficulty": "easy",
    },
    {
        "question": "How many of each power unit element is a driver typically allowed per season before a grid penalty?",
        "options": ["1", "2", "4", "6"],
        "correct": 2,
        "explanation": "Drivers are generally allowed 4 of each power unit element per season without penalty.",
        "category": "rules",
        "difficulty": "hard",
    },
    {
        "question": "What does 'parc ferme' regulate?",
        "options": [
            "Where fans can park",
            "Restrictions on car setup changes after qualifying",
            "Pit lane speed limits",
            "Tyre allocation",
        ],
        "correct": 1,
        "explanation": "Parc fermé rules lock in most car setup parameters between qualifying and the race.",
        "category": "rules",
        "difficulty": "medium",
    },
    {
        "question": "What is the minimum weight limit for a current F1 car (with driver, without fuel), roughly?",
        "options": ["~600 kg", "~798 kg", "~900 kg", "~1050 kg"],
        "correct": 1,
        "explanation": "The 2024 minimum weight limit is 798 kg, up significantly due to hybrid components.",
        "category": "rules",
        "difficulty": "hard",
    },
    {
        "question": "What color flag indicates a session has been stopped?",
        "options": ["Yellow", "Blue", "Red", "Black and white"],
        "correct": 2,
        "explanation": "A red flag halts the session immediately, usually for a serious incident or unsafe conditions.",
        "category": "rules",
        "difficulty": "easy",
    },
    {
        "question": "What does a black flag with an orange circle mean?",
        "options": [
            "Mechanical problem, must pit",
            "Race is finished",
            "Overtaking allowed everywhere",
            "Track is wet",
        ],
        "correct": 0,
        "explanation": "The black-and-orange 'meatball' flag tells a driver their car has a mechanical issue and to pit.",
        "category": "rules",
        "difficulty": "medium",
    },

    # ---------------- MEME / ICONIC MOMENTS ----------------
    {
        "question": "\"Bwoah\" is a catchphrase most associated with which F1 personality?",
        "options": ["Kimi Raikkonen", "Nico Rosberg", "David Croft", "Toto Wolff"],
        "correct": 1,
        "explanation": "Nico Rosberg's exaggerated 'bwoah' became a widely-memed F1 sound bite.",
        "category": "meme",
        "difficulty": "medium",
    },
    {
        "question": "Which team was involved in the infamous 'Crashgate' scandal at the 2008 Singapore GP?",
        "options": ["McLaren", "Renault", "Ferrari", "BMW Sauber"],
        "correct": 1,
        "explanation": "Renault's Nelson Piquet Jr. deliberately crashed to help teammate Fernando Alonso win.",
        "category": "meme",
        "difficulty": "medium",
    },
    {
        "question": "\"Leave me alone, I know what I'm doing\" is a famous radio message from which driver?",
        "options": ["Kimi Raikkonen", "Sebastian Vettel", "Lewis Hamilton", "Max Verstappen"],
        "correct": 0,
        "explanation": "Kimi Raikkonen's blunt radio messages are legendary, this one from the 2012 Abu Dhabi GP.",
        "category": "meme",
        "difficulty": "easy",
    },
    {
        "question": "Which team principal's unbuttoned, untucked shirt became a running fan meme?",
        "options": ["Christian Horner", "Toto Wolff", "Guenther Steiner", "Zak Brown"],
        "correct": 1,
        "explanation": "Toto Wolff's shirt style is a well-known running joke among F1 fans.",
        "category": "meme",
        "difficulty": "medium",
    },
    {
        "question": "Which team's colorful, blunt team principal became a breakout star of 'Drive to Survive'?",
        "options": ["Guenther Steiner (Haas)", "Otmar Szafnauer", "Franz Tost", "Andreas Seidl"],
        "correct": 0,
        "explanation": "Guenther Steiner's fiery quotes on Drive to Survive made him a fan-favorite meme figure.",
        "category": "meme",
        "difficulty": "easy",
    },
    {
        "question": "The 2021 Silverstone Copse corner lap-1 crash famously involved Verstappen and which other driver?",
        "options": ["Sergio Perez", "Lewis Hamilton", "Charles Leclerc", "Lando Norris"],
        "correct": 1,
        "explanation": "Hamilton and Verstappen collided at Copse on lap 1 of the 2021 British GP.",
        "category": "meme",
        "difficulty": "easy",
    },
    {
        "question": "Which driver earned a reputation as F1's tyre-management 'smooth operator', nicknamed 'Minister of Defense'?",
        "options": ["Sergio Perez", "Lance Stroll", "Nico Hulkenberg", "Yuki Tsunoda"],
        "correct": 0,
        "explanation": "Sergio Perez earned the 'Minister of Defense' reputation for late-race tyre management and defending.",
        "category": "meme",
        "difficulty": "hard",
    },
    {
        "question": "Which chaotic, rain-soaked 2008 race saw Sebastian Vettel score Toro Rosso's only ever win?",
        "options": ["Monaco GP", "Italian GP", "Brazilian GP", "British GP"],
        "correct": 1,
        "explanation": "The 2008 Italian GP at Monza saw torrential rain and Sebastian Vettel's shock maiden win.",
        "category": "meme",
        "difficulty": "medium",
    },
    {
        "question": "Which team's iconic radio call 'Fernando is faster than you' became one of F1's biggest memes (2010)?",
        "options": ["Red Bull", "McLaren", "Ferrari", "Mercedes"],
        "correct": 1,
        "explanation": "McLaren's 2010 German GP call about Alonso became one of F1's all-time meme moments.",
        "category": "meme",
        "difficulty": "medium",
    },
    {
        "question": "In wet 2021 Turkish GP conditions, which rookie driver comically slid into the back of the Safety Car?",
        "options": ["Nikita Mazepin", "Mick Schumacher", "Antonio Giovinazzi", "George Russell"],
        "correct": 2,
        "explanation": "Antonio Giovinazzi famously crashed into the Safety Car itself in slippery conditions.",
        "category": "meme",
        "difficulty": "hard",
    },
]


def total_questions() -> int:
    return len(QUESTIONS)


# --------------------------------------------------------------------------
# Want to add your own questions? Just append more dicts to QUESTIONS above,
# following the same format:
#
# QUESTIONS.append({
#     "question": "Your question here?",
#     "options": ["Option A", "Option B", "Option C", "Option D"],
#     "correct": 0,  # index of the right answer
#     "explanation": "Fun fact shown after the answer.",
#     "category": "meme",
#     "difficulty": "medium",  # easy=5pts, medium=10pts, hard=15pts
# })
# --------------------------------------------------------------------------
