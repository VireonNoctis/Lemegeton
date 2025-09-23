#!/usr/bin/env python3
"""
Quick test script for the enhanced affinity calculation system.
This tests the new ultra-sophisticated affinity matching with all the complex weighting systems.
"""

import asyncio
import aiohttp
from unittest.mock import AsyncMock, MagicMock
import math
from collections import Counter

# Mock the necessary imports to test just the affinity calculation
class MockBot:
    def __init__(self):
        pass

class MockCog:
    def __init__(self, bot):
        self.bot = bot

# Import and test the affinity calculation function
import sys
import os
sys.path.append(os.path.dirname(__file__))

# Test data representing two users' AniList data
user1_data = {
    "data": {
        "User": {
            "id": 1,
            "name": "TestUser1",
            "statistics": {
                "anime": {
                    "count": 150,
                    "meanScore": 7.2,
                    "standardDeviation": 1.8,
                    "minutesWatched": 18000,
                    "episodesWatched": 1200,
                    "genres": [
                        {"genre": "Action", "count": 45, "meanScore": 7.5},
                        {"genre": "Drama", "count": 30, "meanScore": 8.0},
                        {"genre": "Comedy", "count": 25, "meanScore": 6.8},
                        {"genre": "Romance", "count": 20, "meanScore": 7.8},
                        {"genre": "Fantasy", "count": 15, "meanScore": 8.2}
                    ],
                    "formats": [
                        {"format": "TV", "count": 80, "meanScore": 7.3},
                        {"format": "MOVIE", "count": 35, "meanScore": 7.8},
                        {"format": "OVA", "count": 20, "meanScore": 6.9},
                        {"format": "SPECIAL", "count": 15, "meanScore": 7.1}
                    ],
                    "scores": [
                        {"score": 10, "count": 8},
                        {"score": 9, "count": 15},
                        {"score": 8, "count": 25},
                        {"score": 7, "count": 40},
                        {"score": 6, "count": 35},
                        {"score": 5, "count": 20},
                        {"score": 4, "count": 7}
                    ]
                }
            },
            "favourites": {
                "anime": {
                    "nodes": [
                        {"id": 1, "title": {"romaji": "Attack on Titan"}},
                        {"id": 2, "title": {"romaji": "Death Note"}},
                        {"id": 3, "title": {"romaji": "Fullmetal Alchemist: Brotherhood"}},
                        {"id": 4, "title": {"romaji": "One Piece"}},
                        {"id": 5, "title": {"romaji": "Naruto"}}
                    ]
                }
            }
        }
    }
}

user2_data = {
    "data": {
        "User": {
            "id": 2,
            "name": "TestUser2",
            "statistics": {
                "anime": {
                    "count": 200,
                    "meanScore": 7.8,
                    "standardDeviation": 1.5,
                    "minutesWatched": 24000,
                    "episodesWatched": 1600,
                    "genres": [
                        {"genre": "Action", "count": 55, "meanScore": 7.9},
                        {"genre": "Drama", "count": 40, "meanScore": 8.2},
                        {"genre": "Romance", "count": 35, "meanScore": 8.1},
                        {"genre": "Comedy", "count": 30, "meanScore": 7.0},
                        {"genre": "Thriller", "count": 25, "meanScore": 8.5}
                    ],
                    "formats": [
                        {"format": "TV", "count": 120, "meanScore": 7.8},
                        {"format": "MOVIE", "count": 45, "meanScore": 8.2},
                        {"format": "OVA", "count": 25, "meanScore": 7.3},
                        {"format": "SPECIAL", "count": 10, "meanScore": 7.5}
                    ],
                    "scores": [
                        {"score": 10, "count": 12},
                        {"score": 9, "count": 22},
                        {"score": 8, "count": 35},
                        {"score": 7, "count": 50},
                        {"score": 6, "count": 45},
                        {"score": 5, "count": 25},
                        {"score": 4, "count": 11}
                    ]
                }
            },
            "favourites": {
                "anime": {
                    "nodes": [
                        {"id": 2, "title": {"romaji": "Death Note"}},  # Overlap with User1
                        {"id": 3, "title": {"romaji": "Fullmetal Alchemist: Brotherhood"}},  # Overlap
                        {"id": 6, "title": {"romaji": "Demon Slayer"}},
                        {"id": 7, "title": {"romaji": "Hunter x Hunter"}},
                        {"id": 8, "title": {"romaji": "My Hero Academia"}}
                    ]
                }
            }
        }
    }
}

def calculate_affinity(user1_data, user2_data):
    """
    Ultra-sophisticated affinity calculation with maximum complexity weighting systems.
    
    This function implements 7 major scoring components with advanced mathematical algorithms:
    1. Favorites Affinity (25% weight) - Advanced overlap analysis with rarity weighting
    2. Consumption Patterns (20% weight) - Multi-dimensional activity analysis
    3. Scoring Compatibility (15% weight) - Gaussian similarity with experience weighting
    4. Genre Affinity (15% weight) - Weighted preference analysis with cosine similarity
    5. Format Preferences (10% weight) - Distribution similarity analysis
    6. Activity Level Compatibility (8% weight) - Logarithmic similarity functions
    7. Balance Factors (7% weight) - Media consumption balance and diversity scoring
    """
    try:
        # Extract user statistics
        user1_stats = user1_data['data']['User']['statistics']['anime']
        user2_stats = user2_data['data']['User']['statistics']['anime']
        user1_favs = user1_data['data']['User']['favourites']['anime']['nodes']
        user2_favs = user2_data['data']['User']['favourites']['anime']['nodes']
        
        # Initialize scoring components
        favorites_score = 0.0
        consumption_score = 0.0
        scoring_compatibility = 0.0
        genre_affinity = 0.0
        format_preference = 0.0
        activity_compatibility = 0.0
        balance_factors = 0.0
        
        # Component 1: Favorites Affinity (25% weight)
        # Advanced overlap analysis with rarity weighting
        user1_fav_ids = {fav['id'] for fav in user1_favs}
        user2_fav_ids = {fav['id'] for fav in user2_favs}
        
        if user1_fav_ids and user2_fav_ids:
            # Calculate weighted Jaccard coefficient with rarity bonus
            overlap = len(user1_fav_ids & user2_fav_ids)
            union = len(user1_fav_ids | user2_fav_ids)
            
            if union > 0:
                # Base Jaccard similarity
                jaccard_sim = overlap / union
                
                # Rarity weighting - shared favorites get exponential bonus
                rarity_weight = 1.0 + (overlap * 0.3)  # Each shared favorite adds 30% bonus
                
                # Experience weighting based on total favorites count
                exp_weight = min(len(user1_fav_ids), len(user2_fav_ids)) / 10.0
                exp_weight = min(exp_weight, 1.0)  # Cap at 1.0
                
                favorites_score = jaccard_sim * rarity_weight * (1.0 + exp_weight)
                favorites_score = min(favorites_score, 1.0)  # Normalize to max 1.0
        
        # Component 2: Consumption Patterns (20% weight)
        # Multi-dimensional activity analysis with logarithmic scaling
        def log_similarity(val1, val2):
            """Logarithmic similarity for handling variable-scale data"""
            if val1 <= 0 or val2 <= 0:
                return 0.0
            log_val1, log_val2 = math.log(val1 + 1), math.log(val2 + 1)
            max_val = max(log_val1, log_val2)
            if max_val == 0:
                return 1.0
            return 1.0 - abs(log_val1 - log_val2) / max_val
        
        count_sim = log_similarity(user1_stats['count'], user2_stats['count'])
        episodes_sim = log_similarity(user1_stats['episodesWatched'], user2_stats['episodesWatched'])
        time_sim = log_similarity(user1_stats['minutesWatched'], user2_stats['minutesWatched'])
        
        # Activity intensity analysis
        user1_intensity = user1_stats['minutesWatched'] / max(user1_stats['count'], 1)
        user2_intensity = user2_stats['minutesWatched'] / max(user2_stats['count'], 1)
        intensity_sim = log_similarity(user1_intensity, user2_intensity)
        
        consumption_score = (count_sim * 0.3 + episodes_sim * 0.3 + time_sim * 0.25 + intensity_sim * 0.15)
        
        # Component 3: Scoring Compatibility (15% weight)
        # Gaussian similarity with experience weighting
        def gaussian_similarity(val1, val2, sigma=1.5):
            """Gaussian similarity function for smooth scoring compatibility"""
            return math.exp(-((val1 - val2) ** 2) / (2 * sigma ** 2))
        
        # Mean score similarity with Gaussian function
        mean_sim = gaussian_similarity(user1_stats['meanScore'], user2_stats['meanScore'], 1.2)
        
        # Standard deviation similarity (scoring pattern consistency)
        std_sim = gaussian_similarity(user1_stats['standardDeviation'], user2_stats['standardDeviation'], 0.8)
        
        # Score distribution analysis using Chi-square-like metric
        user1_scores = {item['score']: item['count'] for item in user1_stats['scores']}
        user2_scores = {item['score']: item['count'] for item in user2_stats['scores']}
        
        # Normalize score distributions
        user1_total = sum(user1_scores.values())
        user2_total = sum(user2_scores.values())
        
        score_dist_sim = 0.0
        if user1_total > 0 and user2_total > 0:
            all_scores = set(user1_scores.keys()) | set(user2_scores.keys())
            chi_square_sum = 0.0
            
            for score in all_scores:
                p1 = user1_scores.get(score, 0) / user1_total
                p2 = user2_scores.get(score, 0) / user2_total
                if p1 + p2 > 0:
                    chi_square_sum += ((p1 - p2) ** 2) / (p1 + p2 + 0.001)  # Small epsilon to avoid division by zero
            
            # Convert chi-square to similarity (lower chi-square = higher similarity)
            score_dist_sim = 1.0 / (1.0 + chi_square_sum)
        
        # Experience weighting for scoring compatibility
        experience_factor = min(user1_stats['count'], user2_stats['count']) / 100.0
        experience_factor = min(experience_factor, 1.0)
        
        scoring_compatibility = (mean_sim * 0.4 + std_sim * 0.3 + score_dist_sim * 0.3) * (1.0 + experience_factor * 0.2)
        scoring_compatibility = min(scoring_compatibility, 1.0)
        
        # Component 4: Genre Affinity (15% weight)
        # Weighted preference analysis with cosine similarity
        def cosine_similarity(vec1, vec2):
            """Cosine similarity for preference vectors"""
            if not vec1 or not vec2:
                return 0.0
            
            # Calculate dot product
            dot_product = sum(vec1[key] * vec2.get(key, 0) for key in vec1.keys())
            
            # Calculate magnitudes
            mag1 = math.sqrt(sum(val ** 2 for val in vec1.values()))
            mag2 = math.sqrt(sum(val ** 2 for val in vec2.values()))
            
            if mag1 == 0 or mag2 == 0:
                return 0.0
            
            return dot_product / (mag1 * mag2)
        
        # Create weighted genre preference vectors
        user1_genres = {item['genre']: item['meanScore'] * math.sqrt(item['count']) for item in user1_stats['genres']}
        user2_genres = {item['genre']: item['meanScore'] * math.sqrt(item['count']) for item in user2_stats['genres']}
        
        genre_similarity = cosine_similarity(user1_genres, user2_genres)
        
        # Genre diversity bonus (reward users who share diverse tastes)
        common_genres = set(user1_genres.keys()) & set(user2_genres.keys())
        diversity_bonus = min(len(common_genres) / 10.0, 0.3)  # Max 30% bonus for genre diversity
        
        genre_affinity = genre_similarity + diversity_bonus
        genre_affinity = min(genre_affinity, 1.0)
        
        # Component 5: Format Preferences (10% weight)
        # Distribution similarity analysis
        user1_formats = {item['format']: item['count'] for item in user1_stats['formats']}
        user2_formats = {item['format']: item['count'] for item in user2_stats['formats']}
        
        # Normalize format distributions
        user1_format_total = sum(user1_formats.values())
        user2_format_total = sum(user2_formats.values())
        
        format_sim = 0.0
        if user1_format_total > 0 and user2_format_total > 0:
            user1_format_norm = {fmt: count / user1_format_total for fmt, count in user1_formats.items()}
            user2_format_norm = {fmt: count / user2_format_total for fmt, count in user2_formats.items()}
            
            format_sim = cosine_similarity(user1_format_norm, user2_format_norm)
        
        format_preference = format_sim
        
        # Component 6: Activity Level Compatibility (8% weight)
        # Logarithmic similarity functions for activity metrics
        def activity_similarity(user1_stats, user2_stats):
            """Calculate activity level similarity using multiple metrics"""
            metrics = []
            
            # Episodes per anime ratio
            user1_ep_ratio = user1_stats['episodesWatched'] / max(user1_stats['count'], 1)
            user2_ep_ratio = user2_stats['episodesWatched'] / max(user2_stats['count'], 1)
            metrics.append(log_similarity(user1_ep_ratio, user2_ep_ratio))
            
            # Minutes per episode ratio
            user1_min_per_ep = user1_stats['minutesWatched'] / max(user1_stats['episodesWatched'], 1)
            user2_min_per_ep = user2_stats['minutesWatched'] / max(user2_stats['episodesWatched'], 1)
            metrics.append(log_similarity(user1_min_per_ep, user2_min_per_ep))
            
            # Overall activity level (total minutes)
            metrics.append(log_similarity(user1_stats['minutesWatched'], user2_stats['minutesWatched']))
            
            return sum(metrics) / len(metrics)
        
        activity_compatibility = activity_similarity(user1_stats, user2_stats)
        
        # Component 7: Balance Factors (7% weight)
        # Media consumption balance and diversity scoring
        def calculate_balance_score(stats):
            """Calculate how balanced/diverse a user's consumption is"""
            # Genre balance (entropy-based)
            genre_counts = [item['count'] for item in stats['genres']]
            total_genres = sum(genre_counts)
            if total_genres > 0:
                genre_probs = [count / total_genres for count in genre_counts]
                genre_entropy = -sum(p * math.log(p + 0.001) for p in genre_probs if p > 0)
            else:
                genre_entropy = 0
            
            # Format balance
            format_counts = [item['count'] for item in stats['formats']]
            total_formats = sum(format_counts)
            if total_formats > 0:
                format_probs = [count / total_formats for count in format_counts]
                format_entropy = -sum(p * math.log(p + 0.001) for p in format_probs if p > 0)
            else:
                format_entropy = 0
            
            # Score distribution balance
            score_counts = [item['count'] for item in stats['scores']]
            total_scores = sum(score_counts)
            if total_scores > 0:
                score_probs = [count / total_scores for count in score_counts]
                score_entropy = -sum(p * math.log(p + 0.001) for p in score_probs if p > 0)
            else:
                score_entropy = 0
            
            # Normalize entropies (approximate max entropy values)
            normalized_genre = genre_entropy / 3.0  # Approx max entropy for typical genre distribution
            normalized_format = format_entropy / 1.5  # Approx max entropy for format distribution
            normalized_score = score_entropy / 2.5  # Approx max entropy for score distribution
            
            return (normalized_genre + normalized_format + normalized_score) / 3.0
        
        user1_balance = calculate_balance_score(user1_stats)
        user2_balance = calculate_balance_score(user2_stats)
        
        # Balance similarity (users with similar diversity levels)
        balance_similarity = 1.0 - abs(user1_balance - user2_balance)
        
        # Diversity bonus (reward highly diverse users)
        diversity_bonus = min((user1_balance + user2_balance) / 2.0, 0.3)
        
        balance_factors = balance_similarity * 0.7 + diversity_bonus * 0.3
        
        # Final weighted score calculation
        weights = {
            'favorites': 0.25,
            'consumption': 0.20,
            'scoring': 0.15,
            'genre': 0.15,
            'format': 0.10,
            'activity': 0.08,
            'balance': 0.07
        }
        
        final_score = (
            favorites_score * weights['favorites'] +
            consumption_score * weights['consumption'] +
            scoring_compatibility * weights['scoring'] +
            genre_affinity * weights['genre'] +
            format_preference * weights['format'] +
            activity_compatibility * weights['activity'] +
            balance_factors * weights['balance']
        )
        
        # Ensure final score is between 0 and 1
        final_score = max(0.0, min(1.0, final_score))
        
        # Create detailed breakdown
        breakdown = {
            'final_score': final_score,
            'components': {
                'favorites_affinity': {
                    'score': favorites_score,
                    'weight': weights['favorites'],
                    'contribution': favorites_score * weights['favorites']
                },
                'consumption_patterns': {
                    'score': consumption_score,
                    'weight': weights['consumption'],
                    'contribution': consumption_score * weights['consumption']
                },
                'scoring_compatibility': {
                    'score': scoring_compatibility,
                    'weight': weights['scoring'],
                    'contribution': scoring_compatibility * weights['scoring']
                },
                'genre_affinity': {
                    'score': genre_affinity,
                    'weight': weights['genre'],
                    'contribution': genre_affinity * weights['genre']
                },
                'format_preferences': {
                    'score': format_preference,
                    'weight': weights['format'],
                    'contribution': format_preference * weights['format']
                },
                'activity_compatibility': {
                    'score': activity_compatibility,
                    'weight': weights['activity'],
                    'contribution': activity_compatibility * weights['activity']
                },
                'balance_factors': {
                    'score': balance_factors,
                    'weight': weights['balance'],
                    'contribution': balance_factors * weights['balance']
                }
            }
        }
        
        return breakdown
        
    except Exception as e:
        print(f"Error calculating affinity: {e}")
        return {
            'final_score': 0.0,
            'error': str(e),
            'components': {}
        }

def main():
    """Test the enhanced affinity calculation system"""
    print("🧮 Testing Ultra-Sophisticated Affinity Calculation System")
    print("=" * 80)
    
    result = calculate_affinity(user1_data, user2_data)
    
    if 'error' in result:
        print(f"❌ Error during calculation: {result['error']}")
        return
    
    print(f"🎯 Final Affinity Score: {result['final_score']:.4f} ({result['final_score']*100:.2f}%)")
    print("\n📊 Detailed Component Breakdown:")
    print("-" * 60)
    
    for component_name, component_data in result['components'].items():
        score = component_data['score']
        weight = component_data['weight']
        contribution = component_data['contribution']
        
        # Color coding based on score
        if score >= 0.8:
            color_indicator = "🟢"
        elif score >= 0.6:
            color_indicator = "🟡"
        elif score >= 0.4:
            color_indicator = "🟠"
        else:
            color_indicator = "🔴"
        
        print(f"{color_indicator} {component_name.replace('_', ' ').title()}:")
        print(f"   Score: {score:.4f} | Weight: {weight:.0%} | Contribution: {contribution:.4f}")
        print()
    
    print("✅ Enhanced Affinity Calculation Test Complete!")
    
    # Additional analysis
    print("\n🔍 Analysis Summary:")
    total_contribution = sum(comp['contribution'] for comp in result['components'].values())
    print(f"Total weighted contribution: {total_contribution:.4f}")
    
    # Find strongest and weakest components
    components = result['components']
    strongest = max(components.items(), key=lambda x: x[1]['score'])
    weakest = min(components.items(), key=lambda x: x[1]['score'])
    
    print(f"Strongest compatibility: {strongest[0].replace('_', ' ').title()} ({strongest[1]['score']:.4f})")
    print(f"Weakest compatibility: {weakest[0].replace('_', ' ').title()} ({weakest[1]['score']:.4f})")

if __name__ == "__main__":
    main()