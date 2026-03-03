
"""
Simple text similarity CLI

Small utility to compute similarity between two input texts using a
binary bag-of-words cosine similarity.


"""

import numpy as np
import re


def clean_text(text):
    """Clean text and split into words (English letters only)."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return text.split()


def similarity_between_texts(text1, text2):
    """Compute similarity between two texts (simple binary bag-of-words).

    Returns cosine similarity between binary vectors built from the
    union of words in both texts.
    """
    # Clean texts
    words1 = clean_text(text1)
    words2 = clean_text(text2)

    # All unique words
    all_words = list(set(words1 + words2))

    # Build binary vectors
    vector1 = [1 if word in words1 else 0 for word in all_words]
    vector2 = [1 if word in words2 else 0 for word in all_words]

    # Convert to numpy arrays
    v1 = np.array(vector1)
    v2 = np.array(vector2)

    # Compute cosine similarity
    dot = np.dot(v1, v2)
    norm = np.linalg.norm(v1) * np.linalg.norm(v2)

    if norm == 0:
        return 0.0
    else:
        return dot / norm


def main():
    print("=" * 40)
    print("🔍 Text Similarity Calculator")
    print("=" * 40)

    while True:
        print("\n📝 Enter the first text (or 'q' to quit):")
        text1 = input(" > ")

        if text1.lower() == 'q':
            print("👋 Goodbye!")
            break

        print("\n📝 Enter the second text (or 'q' to quit):")
        text2 = input(" > ")

        if text2.lower() == 'q':
            print("👋 Goodbye!")
            break

        # Calculate similarity
        similarity = similarity_between_texts(text1, text2)

        print(f"\n✨ Similarity: {similarity*100:.1f}%")
        print("-" * 40)


if __name__ == '__main__':
    main()
