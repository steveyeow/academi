from __future__ import annotations

import os

# Vote threshold: when a book title gets this many upvotes, auto-create & learn
VOTE_THRESHOLD = int(os.getenv("VOTE_THRESHOLD", "3"))

# Scheduled discovery interval in seconds (default 6 hours, 0 to disable)
DISCOVERY_INTERVAL = int(os.getenv("DISCOVERY_INTERVAL", str(6 * 3600)))

# Max books to discover per scheduled run
DISCOVERY_BATCH_SIZE = int(os.getenv("DISCOVERY_BATCH_SIZE", "5"))

# ─── Seed catalog (written to DB on first startup only) ───
BOOK_CATALOG_SEED = [
    {"title": "Thinking, Fast and Slow", "author": "Daniel Kahneman", "isbn": "9780374275631", "category": "Psychology", "description": "Explores the two systems that drive the way we think."},
    {"title": "Sapiens: A Brief History of Humankind", "author": "Yuval Noah Harari", "isbn": "9780062316097", "category": "History", "description": "A sweeping narrative of humanity from the Stone Age to the age of capitalism."},
    {"title": "Surely You're Joking, Mr. Feynman!", "author": "Richard Feynman", "isbn": "9780393355628", "category": "Science", "description": "Adventures of a curious character — the Nobel physicist's autobiography."},
    {"title": "A Brief History of Time", "author": "Stephen Hawking", "isbn": "9780553380163", "category": "Physics", "description": "From the Big Bang to black holes — a landmark volume in science writing."},
    {"title": "The Structure of Scientific Revolutions", "author": "Thomas S. Kuhn", "isbn": "9780226458120", "category": "Philosophy", "description": "How paradigm shifts transform scientific understanding."},
    {"title": "Zero to One", "author": "Peter Thiel", "isbn": "9780804139298", "category": "Business", "description": "Notes on startups, or how to build the future."},
    {"title": "Principles", "author": "Ray Dalio", "isbn": "9781501124020", "category": "Business", "description": "Life and work principles from one of the world's most successful investors."},
    {"title": "Atomic Habits", "author": "James Clear", "isbn": "9780735211292", "category": "Self-help", "description": "An easy way to build good habits and break bad ones."},
    {"title": "Deep Work", "author": "Cal Newport", "isbn": "9781455586691", "category": "Productivity", "description": "Rules for focused success in a distracted world."},
    {"title": "The Lean Startup", "author": "Eric Ries", "isbn": "9780307887894", "category": "Business", "description": "How entrepreneurs use continuous innovation to create successful businesses."},
    {"title": "The Selfish Gene", "author": "Richard Dawkins", "isbn": "9780198788607", "category": "Biology", "description": "The gene-centered view of evolution that revolutionized biology."},
    {"title": "Guns, Germs, and Steel", "author": "Jared Diamond", "isbn": "9780393354324", "category": "History", "description": "Why did history unfold differently on different continents?"},
    {"title": "The Art of War", "author": "Sun Tzu", "isbn": "9781599869773", "category": "Philosophy", "description": "The ancient military treatise that remains influential in strategy."},
    {"title": "Influence", "author": "Robert B. Cialdini", "isbn": "9780062937650", "category": "Psychology", "description": "The psychology of persuasion and the six principles of compliance."},
    {"title": "The Innovator's Dilemma", "author": "Clayton Christensen", "isbn": "9780062060242", "category": "Business", "description": "When new technologies cause great firms to fail."},
    {"title": "Meditations", "author": "Marcus Aurelius", "isbn": "9780140449334", "category": "Philosophy", "description": "Stoic reflections on life, death, and virtue by a Roman Emperor."},
    {"title": "1984", "author": "George Orwell", "isbn": "9780451524935", "category": "Fiction", "description": "A dystopian masterpiece about totalitarianism and surveillance."},
    {"title": "The Wealth of Nations", "author": "Adam Smith", "isbn": "9780679783367", "category": "Economics", "description": "The foundational work of classical economics."},
    {"title": "Homo Deus", "author": "Yuval Noah Harari", "isbn": "9780062464316", "category": "History", "description": "A brief history of tomorrow — what happens when myths meet technology."},
    {"title": "The Black Swan", "author": "Nassim Nicholas Taleb", "isbn": "9780812973815", "category": "Philosophy", "description": "The impact of the highly improbable."},
    {"title": "Brave New World", "author": "Aldous Huxley", "isbn": "9780060850524", "category": "Fiction", "description": "A dystopian vision where humanity is subdued by pleasure and comfort."},
    {"title": "Good to Great", "author": "Jim Collins", "isbn": "9780066620992", "category": "Business", "description": "Why some companies make the leap to sustained excellence."},
    {"title": "The Republic", "author": "Plato", "isbn": "9780140455113", "category": "Philosophy", "description": "Plato's foundational work on justice and the ideal state."},
    {"title": "Cosmos", "author": "Carl Sagan", "isbn": "9780345539434", "category": "Science", "description": "The story of the universe and our place within it."},
]
