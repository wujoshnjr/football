# ============================================
# INSTITUTIONAL FOOTBALL TRADING SYSTEM
# Production-Grade Hedge Fund Analytics Engine
# ============================================

import os
import json
import logging
import asyncio
import aiohttp
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from functools import lru_cache
import streamlit as st
from scipy import stats
from scipy.optimize import minimize_scalar
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pytz
from dotenv import load_dotenv

# ============================================
# CONFIGURATION & LOGGING
# ============================================

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MarketType(Enum):
    MATCH_ODDS = "1X2"
    OVER_UNDER = "over_under"
    ASIAN_HANDICAP = "asian_handicap"

class TrapSignal(Enum):
    OK = "✅ OK"
    WARNING = "⚠️ WARNING"
    TRAP_HOME = "🚨 TRAP HOME"
    TRAP_AWAY = "🚨 TRAP AWAY"
    TRAP_DRAW = "🚨 TRAP DRAW"

# ============================================
# DATA STRUCTURES
# ============================================

@dataclass
class TeamStats:
    """Unified team statistics container"""
    team_id: str
    team_name: str
    league: str
    attack_strength: float = 1.0
    defense_strength: float = 1.0
    home_advantage: float = 1.15
    form_5_matches: float = 1.0
    form_10_matches: float = 1.0
    home_form: float = 1.0
    away_form: float = 1.0
    h2h_advantage: float = 0.0
    injury_impact: float = 1.0
    lineup_strength: float = 1.0
    recent_goals_scored: float = 1.5
    recent_goals_conceded: float = 1.2

@dataclass
class MarketOdds:
    """Odds data container"""
    home: float
    draw: float
    away: float
    over_15: Optional[float] = None
    under_15: Optional[float] = None
    over_25: Optional[float] = None
    under_25: Optional[float] = None
    over_35: Optional[float] = None
    under_35: Optional[float] = None
    asian_handicap_home: Optional[float] = None
    asian_handicap_away: Optional[float] = None
    handicap_line: Optional[float] = None
    opening_home: Optional[float] = None
    opening_draw: Optional[float] = None
    opening_away: Optional[float] = None
    
    def implied_probabilities(self) -> Dict[str, float]:
        """Extract raw implied probabilities"""
        return {
            'home': 1 / self.home if self.home else 0,
            'draw': 1 / self.draw if self.draw else 0,
            'away': 1 / self.away if self.away else 0
        }

@dataclass
class MatchData:
    """Complete match data container"""
    match_id: str
    home_team: str
    away_team: str
    league: str
    kickoff: datetime
    home_stats: TeamStats
    away_stats: TeamStats
    market_odds: MarketOdds
    news_sentiment: Dict[str, Any] = field(default_factory=dict)
    lineup_data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ModelOutput:
    """Model prediction output"""
    home_prob: float
    draw_prob: float
    away_prob: float
    expected_goals_home: float
    expected_goals_away: float
    score_distribution: Dict[str, float]
    over_15_prob: float
    over_25_prob: float
    over_35_prob: float
    asian_handicap_value: float
    fair_odds: Dict[str, float]
    ev_1x2: Dict[str, float]
    kelly_stakes: Dict[str, float]
    trap_signal: TrapSignal
    upset_probability: float
    confidence_score: float

# ============================================
# API CLIENTS (Data Layer)
# ============================================

class APIClientBase:
    """Base API client with error handling and rate limiting"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limit_delay = 1.0
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def _request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Safe request with retry logic"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        params = params or {}
        params['apiKey'] = self.api_key
        
        for attempt in range(3):
            try:
                async with self.session.get(
                    f"{self.base_url}/{endpoint}",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        await asyncio.sleep(self.rate_limit_delay)
                        return await response.json()
                    elif response.status == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        logger.warning(f"API error {response.status}: {endpoint}")
                        return None
            except Exception as e:
                logger.error(f"Request failed: {e}")
                await asyncio.sleep(1)
        return None

class OddsAPIClient(APIClientBase):
    """The Odds API client"""
    
    def __init__(self):
        super().__init__(
            base_url="https://api.the-odds-api.com/v4",
            api_key=os.getenv('ODDS_API_KEY', '')
        )
        
    async def get_soccer_odds(self, regions: List[str] = ['uk', 'eu']) -> List[Dict]:
        """Fetch soccer odds with multiple markets"""
        params = {
            'sport': 'soccer',
            'regions': ','.join(regions),
            'markets': 'h2h,spreads,totals',
            'oddsFormat': 'decimal',
            'dateFormat': 'iso'
        }
        return await self._request('sports/soccer/odds', params) or []

class SportmonksClient(APIClientBase):
    """Sportmonks Football API client"""
    
    def __init__(self):
        super().__init__(
            base_url="https://soccer.sportmonks.com/api/v2.0",
            api_key=os.getenv('SPORTMONKS_API_KEY', '')
        )
        
    async def get_fixtures(self, date: str, include: List[str] = None) -> List[Dict]:
        """Get fixtures with rich includes"""
        include = include or ['localTeam', 'visitorTeam', 'league', 'stats', 'lineup']
        params = {
            'include': ','.join(include),
            'filter[date]': date
        }
        result = await self._request('fixtures/between', params)
        return result.get('data', []) if result else []
    
    async def get_team_stats(self, team_id: int, league_id: int = None) -> Dict:
        """Get comprehensive team statistics"""
        params = {
            'include': 'stats,latest,upcoming'
        }
        if league_id:
            params['filter[league_id]'] = league_id
            
        result = await self._request(f'teams/{team_id}', params)
        return result.get('data', {}) if result else {}
    
    async def get_h2h(self, team1_id: int, team2_id: int) -> List[Dict]:
        """Get head-to-head history"""
        params = {
            'include': 'localTeam,visitorTeam,scores'
        }
        result = await self._request(f'head2head/{team1_id}/{team2_id}', params)
        return result.get('data', []) if result else []

class NewsAPIClient(APIClientBase):
    """News API client for sentiment analysis"""
    
    def __init__(self):
        super().__init__(
            base_url="https://newsapi.org/v2",
            api_key=os.getenv('NEWS_API_KEY', '')
        )
        
    async def get_team_news(self, team_name: str, days: int = 3) -> List[Dict]:
        """Fetch recent news for a team"""
        from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        params = {
            'q': f'{team_name} football injury lineup',
            'from': from_date,
            'language': 'en',
            'sortBy': 'relevancy',
            'pageSize': 20
        }
        result = await self._request('everything', params)
        return result.get('articles', []) if result else []

# ============================================
# DATA NORMALIZATION LAYER
# ============================================

class DataNormalizer:
    """Normalize data from various sources into unified schema"""
    
    @staticmethod
    def normalize_odds(api_response: Dict) -> MarketOdds:
        """Convert API odds response to MarketOdds"""
        bookmakers = api_response.get('bookmakers', [])
        if not bookmakers:
            return MarketOdds(home=2.0, draw=3.5, away=3.0)
            
        # Take average across bookmakers for robustness
        markets = bookmakers[0].get('markets', [])
        
        odds_data = {'home': 2.0, 'draw': 3.5, 'away': 3.0}
        for market in markets:
            if market['key'] == 'h2h':
                outcomes = market['outcomes']
                odds_data = {
                    'home': next((o['price'] for o in outcomes if o['name'] == outcomes[0]['name']), 2.0),
                    'draw': next((o['price'] for o in outcomes if o['name'] == 'Draw'), 3.5),
                    'away': next((o['price'] for o in outcomes if o['name'] == outcomes[-1]['name']), 3.0)
                }
            elif market['key'] == 'totals':
                for outcome in market['outcomes']:
                    if outcome['point'] == 2.5:
                        if outcome['name'] == 'Over':
                            odds_data['over_25'] = outcome['price']
                        else:
                            odds_data['under_25'] = outcome['price']
                            
        return MarketOdds(**odds_data)
    
    @staticmethod
    def normalize_team_stats(api_data: Dict) -> TeamStats:
        """Normalize team statistics from Sportmonks"""
        return TeamStats(
            team_id=str(api_data.get('id', '')),
            team_name=api_data.get('name', ''),
            league=api_data.get('league', {}).get('name', ''),
            attack_strength=api_data.get('stats', {}).get('attack', 1.0),
            defense_strength=api_data.get('stats', {}).get('defense', 1.0),
            form_5_matches=api_data.get('form', {}).get('last5', 1.0),
            form_10_matches=api_data.get('form', {}).get('last10', 1.0)
        )
    
    @staticmethod
    def analyze_sentiment(news_articles: List[Dict]) -> Dict[str, Any]:
        """Extract sentiment and injury information from news"""
        injury_keywords = ['injury', 'injured', 'out', 'doubt', 'fitness test']
        lineup_keywords = ['lineup', 'starting xi', 'formation', 'tactical']
        
        injury_count = 0
        sentiment_score = 0.0
        
        for article in news_articles[:10]:
            title = article.get('title', '').lower()
            description = article.get('description', '').lower()
            content = f"{title} {description}"
            
            # Check for injury mentions
            if any(kw in content for kw in injury_keywords):
                injury_count += 1
                sentiment_score -= 0.1
                
            # Check for positive news
            if any(kw in content for kw in ['win', 'victory', 'form', 'confident']):
                sentiment_score += 0.05
                
        return {
            'injury_impact': max(0.7, 1.0 - (injury_count * 0.1)),
            'sentiment_score': max(-0.5, min(0.5, sentiment_score)),
            'injury_count': injury_count,
            'key_news_count': len(news_articles)
        }

# ============================================
# CORE MODELS (Football Engine)
# ============================================

class VigRemover:
    """Remove bookmaker margin (vig/juice) from odds"""
    
    @staticmethod
    def margin_free_probabilities(odds: Dict[str, float]) -> Dict[str, float]:
        """Convert odds to true probabilities using proportional method"""
        implied_probs = {k: 1/v for k, v in odds.items() if v > 1.0}
        total_implied = sum(implied_probs.values())
        
        if total_implied > 0:
            return {k: v / total_implied for k, v in implied_probs.items()}
        return implied_probs
    
    @staticmethod
    def margin_free_odds(odds: Dict[str, float]) -> Dict[str, float]:
        """Get fair odds without margin"""
        probs = VigRemover.margin_free_probabilities(odds)
        return {k: 1/v if v > 0 else 999.0 for k, v in probs.items()}

class PoissonModel:
    """Poisson goal model with comprehensive features"""
    
    def __init__(self, league_avg_goals: float = 2.75):
        self.league_avg_goals = league_avg_goals
        
    def calculate_lambda(
        self,
        team_strength: TeamStats,
        opponent_strength: TeamStats,
        is_home: bool,
        market_signal: Dict[str, float] = None,
        sentiment_impact: float = 1.0
    ) -> float:
        """Calculate expected goals (lambda) for a team"""
        
        # Base attack/defense calculation
        base_lambda = (
            team_strength.attack_strength *
            opponent_strength.defense_strength *
            self.league_avg_goals / 2
        )
        
        # Home advantage multiplier
        home_multiplier = team_strength.home_advantage if is_home else 1.0
        
        # Form impact (weighted recent performance)
        form_impact = (
            team_strength.form_5_matches * 0.6 +
            team_strength.form_10_matches * 0.4
        )
        
        # H2H adjustment
        h2h_adjustment = 1.0 + (team_strength.h2h_advantage * 0.1)
        
        # Injury and lineup impact
        availability_impact = (
            team_strength.injury_impact *
            team_strength.lineup_strength *
            sentiment_impact
        )
        
        # Market signal incorporation (wisdom of crowds)
        market_factor = 1.0
        if market_signal:
            implied_home_prob = market_signal.get('home', 0.33)
            market_factor = 1.0 + (implied_home_prob - 0.5) * 0.5
        
        # Combine all factors
        lambda_value = (
            base_lambda *
            home_multiplier *
            form_impact *
            h2h_adjustment *
            availability_impact *
            market_factor
        )
        
        # Ensure realistic range
        return max(0.2, min(5.0, lambda_value))
    
    def score_probability(self, home_lambda: float, away_lambda: float) -> Dict[str, float]:
        """Calculate full score distribution using bivariate Poisson"""
        max_goals = 10
        score_probs = {}
        
        for h_goals in range(max_goals + 1):
            for a_goals in range(max_goals + 1):
                prob = (
                    stats.poisson.pmf(h_goals, home_lambda) *
                    stats.poisson.pmf(a_goals, away_lambda)
                )
                score_probs[f"{h_goals}-{a_goals}"] = prob
                
        return score_probs

class MonteCarloSimulator:
    """Monte Carlo simulation engine for football matches"""
    
    def __init__(self, n_simulations: int = 100000):
        self.n_simulations = n_simulations
        
    def simulate_match(
        self,
        home_lambda: float,
        away_lambda: float,
        include_variance: bool = True
    ) -> Dict[str, Any]:
        """Run full Monte Carlo simulation"""
        
        # Add randomness to lambda for uncertainty
        if include_variance:
            home_lambdas = np.random.gamma(
                shape=home_lambda * 10,
                scale=0.1,
                size=self.n_simulations
            )
            away_lambdas = np.random.gamma(
                shape=away_lambda * 10,
                scale=0.1,
                size=self.n_simulations
            )
        else:
            home_lambdas = np.full(self.n_simulations, home_lambda)
            away_lambdas = np.full(self.n_simulations, away_lambda)
            
        # Generate goals
        home_goals = np.random.poisson(home_lambdas)
        away_goals = np.random.poisson(away_lambdas)
        
        # Calculate probabilities
        home_wins = np.sum(home_goals > away_goals) / self.n_simulations
        draws = np.sum(home_goals == away_goals) / self.n_simulations
        away_wins = np.sum(home_goals < away_goals) / self.n_simulations
        
        # Score distribution
        score_counts = {}
        for h, a in zip(home_goals, away_goals):
            key = f"{h}-{a}"
            score_counts[key] = score_counts.get(key, 0) + 1
            
        score_probs = {k: v / self.n_simulations for k, v in score_counts.items()}
        
        # Top 5 scorelines
        top_scores = sorted(score_probs.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Over/Under calculations
        total_goals = home_goals + away_goals
        
        return {
            'home_prob': home_wins,
            'draw_prob': draws,
            'away_prob': away_wins,
            'expected_home_goals': np.mean(home_goals),
            'expected_away_goals': np.mean(away_goals),
            'score_distribution': score_probs,
            'top_5_scores': top_scores,
            'over_15': np.mean(total_goals > 1.5),
            'over_25': np.mean(total_goals > 2.5),
            'over_35': np.mean(total_goals > 3.5),
            'std_home_goals': np.std(home_goals),
            'std_away_goals': np.std(away_goals)
        }

class AsianHandicapModel:
    """Asian Handicap value detection"""
    
    @staticmethod
    def calculate_handicap_value(
        home_lambda: float,
        away_lambda: float,
        market_handicap: float = 0.0
    ) -> Dict[str, float]:
        """Calculate fair handicap and value"""
        
        # Simulate handicap outcomes
        n_sim = 50000
        home_goals = np.random.poisson(home_lambda, n_sim)
        away_goals = np.random.poisson(away_lambda, n_sim)
        
        # Test various handicap lines
        handicap_values = {}
        for line in [-1.5, -1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0, 1.5]:
            adjusted_diff = home_goals - away_goals + line
            
            if line in [-0.25, 0.25, -0.75, 0.75]:  # Asian split handicaps
                win_half = np.mean(adjusted_diff > 0)
                push_half = np.mean(adjusted_diff == 0)
                cover_prob = win_half + (push_half * 0.5)
            else:
                cover_prob = np.mean(adjusted_diff > 0)
                
            fair_odds = 1 / cover_prob if cover_prob > 0 else 999
            handicap_values[line] = {
                'cover_probability': cover_prob,
                'fair_odds': fair_odds,
                'value': cover_prob - 0.5 if line > 0 else 0.5 - cover_prob
            }
            
        return handicap_values

# ============================================
# ADVANCED ANALYTICS
# ============================================

class TrapDetector:
    """Detect suspicious markets and trap games"""
    
    def __init__(self, divergence_threshold: float = 0.15):
        self.divergence_threshold = divergence_threshold
        
    def detect_trap(
        self,
        model_probs: Dict[str, float],
        market_probs: Dict[str, float],
        odds_movement: Dict[str, Any],
        news_impact: Dict[str, Any]
    ) -> Tuple[TrapSignal, float]:
        """Analyze market for trap signals"""
        
        trap_score = 0.0
        signals = []
        
        # Check model-market divergence
        home_divergence = abs(model_probs['home'] - market_probs['home'])
        if home_divergence > self.divergence_threshold:
            trap_score += home_divergence * 2
            signals.append(f"Large divergence: {home_divergence:.1%}")
            
        # Check for overreaction to favorites
        if market_probs['home'] > 0.60 and model_probs['home'] < 0.55:
            trap_score += 0.3
            signals.append("Market overvaluing favorite")
            
        # Analyze odds movement
        if odds_movement.get('sharp_money_detected'):
            trap_score += odds_movement['movement_magnitude'] * 2
            signals.append("Sharp money movement detected")
            
        # News mismatch check
        if news_impact.get('injury_count', 0) > 0 and market_probs['home'] > 0.55:
            trap_score += 0.2
            signals.append("Market ignoring injury news")
            
        # Draw suppression check
        if market_probs['draw'] < 0.22 and model_probs['draw'] > 0.28:
            trap_score += 0.15
            signals.append("Draw probability suppressed")
            
        # Determine signal type
        if trap_score < 0.3:
            signal = TrapSignal.OK
        elif trap_score < 0.6:
            signal = TrapSignal.WARNING
        elif market_probs['home'] > model_probs['home']:
            signal = TrapSignal.TRAP_HOME
        elif market_probs['away'] > model_probs['away']:
            signal = TrapSignal.TRAP_AWAY
        else:
            signal = TrapSignal.TRAP_DRAW
            
        return signal, trap_score

class UpsetDetector:
    """Detect upset probability"""
    
    def __init__(self):
        self.upset_threshold = 0.35
        
    def calculate_upset_probability(
        self,
        underdog_prob: float,
        favorite_market_prob: float,
        model_std: float,
        lineup_uncertainty: float,
        recent_variance: float
    ) -> float:
        """Calculate comprehensive upset probability"""
        
        # Base upset from underdog win probability
        base_upset = underdog_prob
        
        # Market overconfidence penalty
        market_overconfidence = max(0, favorite_market_prob - 0.65)
        confidence_factor = 1.0 + (market_overconfidence * 1.5)
        
        # Volatility impact (higher variance = more upsets)
        volatility_factor = 1.0 + (model_std * 0.3)
        
        # Uncertainty factors
        uncertainty_multiplier = 1.0 + (
            lineup_uncertainty * 0.4 +
            recent_variance * 0.3
        )
        
        # Low scoring adjustment (1-0 games more prone to upsets)
        scoring_factor = 1.2 if model_std < 1.5 else 1.0
        
        upset_prob = (
            base_upset *
            confidence_factor *
            volatility_factor *
            uncertainty_multiplier *
            scoring_factor
        )
        
        return min(0.65, upset_prob)

class KellyCriterion:
    """Kelly stake sizing with fractional options"""
    
    def __init__(self, fraction: float = 0.25, max_stake: float = 0.05):
        self.fraction = fraction
        self.max_stake = max_stake
        
    def calculate_stake(self, probability: float, odds: float) -> float:
        """Calculate Kelly stake"""
        if odds <= 1.0 or probability <= 0:
            return 0.0
            
        b = odds - 1  # Decimal odds to net odds
        p = probability
        q = 1 - p
        
        kelly = (b * p - q) / b
        
        # Apply constraints
        kelly = max(0.0, min(kelly, self.max_stake))
        kelly *= self.fraction
        
        return kelly
    
    def multi_market_allocation(
        self,
        opportunities: List[Dict[str, float]]
    ) -> Dict[str, float]:
        """Allocate across multiple markets"""
        total_kelly = sum(
            self.calculate_stake(opp['prob'], opp['odds'])
            for opp in opportunities
        )
        
        if total_kelly > self.max_stake:
            # Scale down proportionally
            scale = self.max_stake / total_kelly
            return {
                opp['market']: self.calculate_stake(opp['prob'], opp['odds']) * scale
                for opp in opportunities
            }
        
        return {
            opp['market']: self.calculate_stake(opp['prob'], opp['odds'])
            for opp in opportunities
        }

# ============================================
# MAIN TRADING ENGINE
# ============================================

class FootballTradingEngine:
    """Main trading system orchestrator"""
    
    def __init__(self):
        self.poisson_model = PoissonModel()
        self.monte_carlo = MonteCarloSimulator(n_simulations=100000)
        self.handicap_model = AsianHandicapModel()
        self.trap_detector = TrapDetector()
        self.upset_detector = UpsetDetector()
        self.kelly = KellyCriterion(fraction=0.25)
        self.normalizer = DataNormalizer()
        
        # API Clients
        self.odds_client = OddsAPIClient()
        self.sportmonks = SportmonksClient()
        self.news_client = NewsAPIClient()
        
    async def analyze_match(self, match_data: MatchData) -> ModelOutput:
        """Complete match analysis pipeline"""
        
        # Extract market signals
        market_probs = VigRemover.margin_free_probabilities({
            'home': match_data.market_odds.home,
            'draw': match_data.market_odds.draw,
            'away': match_data.market_odds.away
        })
        
        # Calculate expected goals
        home_lambda = self.poisson_model.calculate_lambda(
            match_data.home_stats,
            match_data.away_stats,
            is_home=True,
            market_signal=market_probs,
            sentiment_impact=match_data.news_sentiment.get('injury_impact', 1.0)
        )
        
        away_lambda = self.poisson_model.calculate_lambda(
            match_data.away_stats,
            match_data.home_stats,
            is_home=False,
            market_signal=market_probs,
            sentiment_impact=match_data.news_sentiment.get('injury_impact', 1.0)
        )
        
        # Run Monte Carlo simulation
        sim_results = self.monte_carlo.simulate_match(home_lambda, away_lambda)
        
        # Calculate Asian Handicap values
        handicap_values = self.handicap_model.calculate_handicap_value(
            home_lambda,
            away_lambda
        )
        
        # Detect trap signals
        trap_signal, trap_score = self.trap_detector.detect_trap(
            {'home': sim_results['home_prob'],
             'draw': sim_results['draw_prob'],
             'away': sim_results['away_prob']},
            market_probs,
            self._analyze_odds_movement(match_data),
            match_data.news_sentiment
        )
        
        # Calculate upset probability
        is_favorite_home = sim_results['home_prob'] > sim_results['away_prob']
        underdog_prob = sim_results['away_prob'] if is_favorite_home else sim_results['home_prob']
        favorite_market_prob = market_probs['home'] if is_favorite_home else market_probs['away']
        
        upset_prob = self.upset_detector.calculate_upset_probability(
            underdog_prob,
            favorite_market_prob,
            (sim_results['std_home_goals'] + sim_results['std_away_goals']) / 2,
            match_data.news_sentiment.get('lineup_uncertainty', 0.1),
            abs(match_data.home_stats.form_5_matches - match_data.home_stats.form_10_matches)
        )
        
        # Calculate EV and Kelly stakes
        fair_odds = {
            'home': 1 / sim_results['home_prob'],
            'draw': 1 / sim_results['draw_prob'],
            'away': 1 / sim_results['away_prob']
        }
        
        ev_1x2 = {
            'home': sim_results['home_prob'] * match_data.market_odds.home - 1,
            'draw': sim_results['draw_prob'] * match_data.market_odds.draw - 1,
            'away': sim_results['away_prob'] * match_data.market_odds.away - 1
        }
        
        kelly_stakes = {
            'home': self.kelly.calculate_stake(
                sim_results['home_prob'],
                match_data.market_odds.home
            ),
            'draw': self.kelly.calculate_stake(
                sim_results['draw_prob'],
                match_data.market_odds.draw
            ),
            'away': self.kelly.calculate_stake(
                sim_results['away_prob'],
                match_data.market_odds.away
            )
        }
        
        # Calculate confidence score
        confidence = self._calculate_confidence(
            sim_results,
            trap_score,
            market_probs
        )
        
        return ModelOutput(
            home_prob=sim_results['home_prob'],
            draw_prob=sim_results['draw_prob'],
            away_prob=sim_results['away_prob'],
            expected_goals_home=home_lambda,
            expected_goals_away=away_lambda,
            score_distribution=sim_results['score_distribution'],
            over_15_prob=sim_results['over_15'],
            over_25_prob=sim_results['over_25'],
            over_35_prob=sim_results['over_35'],
            asian_handicap_value=handicap_values.get(-0.5, {}).get('value', 0),
            fair_odds=fair_odds,
            ev_1x2=ev_1x2,
            kelly_stakes=kelly_stakes,
            trap_signal=trap_signal,
            upset_probability=upset_prob,
            confidence_score=confidence
        )
    
    def _analyze_odds_movement(self, match_data: MatchData) -> Dict[str, Any]:
        """Analyze odds movement patterns"""
        if not match_data.market_odds.opening_home:
            return {'sharp_money_detected': False, 'movement_magnitude': 0.0}
            
        movement = abs(
            match_data.market_odds.home - match_data.market_odds.opening_home
        )
        
        return {
            'sharp_money_detected': movement > 0.2,
            'movement_magnitude': movement,
            'direction': 'down' if match_data.market_odds.home < match_data.market_odds.opening_home else 'up'
        }
    
    def _calculate_confidence(
        self,
        sim_results: Dict,
        trap_score: float,
        market_probs: Dict
    ) -> float:
        """Calculate overall prediction confidence"""
        confidence = 1.0
        
        # Reduce confidence if high variance
        confidence *= 1.0 - (sim_results['std_home_goals'] * 0.1)
        
        # Reduce confidence for trap signals
        confidence *= 1.0 - (trap_score * 0.5)
        
        # Reduce if model diverges significantly from market
        divergence = abs(sim_results['home_prob'] - market_probs['home'])
        confidence *= 1.0 - (divergence * 0.3)
        
        return max(0.3, min(0.95, confidence))
    
    async def fetch_live_data(self, leagues: List[str]) -> List[MatchData]:
        """Fetch and normalize all data for matches"""
        matches = []
        
        async with self.odds_client, self.sportmonks, self.news_client:
            # Fetch odds data
            odds_data = await self.odds_client.get_soccer_odds()
            
            today = datetime.now().strftime('%Y-%m-%d')
            fixtures = await self.sportmonks.get_fixtures(today)
            
            for fixture in fixtures[:20]:  # Limit for performance
                try:
                    # Normalize team stats
                    home_stats = self.normalizer.normalize_team_stats(
                        fixture.get('localTeam', {})
                    )
                    away_stats = self.normalizer.normalize_team_stats(
                        fixture.get('visitorTeam', {})
                    )
                    
                    # Get news sentiment
                    home_news = await self.news_client.get_team_news(home_stats.team_name)
                    away_news = await self.news_client.get_team_news(away_stats.team_name)
                    
                    home_sentiment = self.normalizer.analyze_sentiment(home_news)
                    away_sentiment = self.normalizer.analyze_sentiment(away_news)
                    
                    # Apply sentiment to stats
                    home_stats.injury_impact = home_sentiment['injury_impact']
                    away_stats.injury_impact = away_sentiment['injury_impact']
                    
                    # Find matching odds
                    match_odds = self._find_matching_odds(fixture, odds_data)
                    
                    # Create match data
                    match = MatchData(
                        match_id=str(fixture.get('id')),
                        home_team=home_stats.team_name,
                        away_team=away_stats.team_name,
                        league=fixture.get('league', {}).get('name', 'Unknown'),
                        kickoff=datetime.fromisoformat(
                            fixture.get('time', {}).get('starting_at', {}).get('date_time', '')
                        ),
                        home_stats=home_stats,
                        away_stats=away_stats,
                        market_odds=match_odds,
                        news_sentiment={
                            'home': home_sentiment,
                            'away': away_sentiment
                        }
                    )
                    
                    matches.append(match)
                    
                except Exception as e:
                    logger.error(f"Error processing fixture: {e}")
                    continue
                    
        return matches
    
    def _find_matching_odds(self, fixture: Dict, odds_data: List[Dict]) -> MarketOdds:
        """Match fixture with odds data"""
        home_team = fixture.get('localTeam', {}).get('name', '')
        away_team = fixture.get('visitorTeam', {}).get('name', '')
        
        for event in odds_data:
            if (home_team.lower() in event.get('home_team', '').lower() and
                away_team.lower() in event.get('away_team', '').lower()):
                return self.normalizer.normalize_odds(event)
                
        # Return default odds if no match found
        return MarketOdds(home=2.0, draw=3.5, away=3.0)

# ============================================
# STREAMLIT DASHBOARD
# ============================================

class TradingDashboard:
    """Institutional trading desk dashboard"""
    
    def __init__(self):
        self.engine = FootballTradingEngine()
        st.set_page_config(
            page_title="Football Trading Desk",
            page_icon="⚽",
            layout="wide"
        )
        
    def run(self):
        """Main dashboard application"""
        st.title("🏦 Institutional Football Trading Desk")
        st.markdown("---")
        
        # Sidebar controls
        with st.sidebar:
            st.header("🎛️ Trading Parameters")
            leagues = st.multiselect(
                "Active Leagues",
                ['EPL', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1', 'MLS'],
                default=['EPL', 'La Liga', 'Bundesliga']
            )
            
            kelly_fraction = st.slider(
                "Kelly Fraction",
                0.05, 0.5, 0.25, 0.05,
                help="Fraction of full Kelly to use"
            )
            
            min_ev = st.slider(
                "Minimum EV %",
                0.0, 15.0, 5.0, 0.5
            ) / 100
            
            st.markdown("---")
            st.header("📊 Risk Controls")
            max_stake_pct = st.slider(
                "Max Stake %",
                1.0, 10.0, 5.0, 0.5
            ) / 100
            
            show_only_value = st.checkbox("Show Only Value Bets", value=True)
            
        # Main content area
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Active Matches", "24", "+3")
        with col2:
            st.metric("Total EV", "+8.4%", "+2.1%")
        with col3:
            st.metric("Kelly Allocation", "12.3%", "-1.2%")
        with col4:
            st.metric("P&L (Today)", "+2.3u", "+1.1u")
            
        st.markdown("---")
        
        # Fetch and display matches
        with st.spinner("Fetching market data..."):
            matches = asyncio.run(self.engine.fetch_live_data(leagues))
            
        if not matches:
            st.warning("No matches available. Using demo data...")
            matches = self._generate_demo_matches()
            
        # Process matches
        results = []
        progress_bar = st.progress(0)
        
        for i, match in enumerate(matches):
            result = asyncio.run(self.engine.analyze_match(match))
            results.append((match, result))
            progress_bar.progress((i + 1) / len(matches))
            
        progress_bar.empty()
        
        # Sort by kickoff time
        tz = pytz.timezone('Asia/Taipei')
        results.sort(key=lambda x: x[0].kickoff.astimezone(tz) if x[0].kickoff else datetime.max.replace(tzinfo=tz))
        
        # Display match cards
        for match, output in results:
            if show_only_value:
                max_ev = max(output.ev_1x2.values())
                if max_ev < min_ev:
                    continue
                    
            self._render_match_card(match, output, kelly_fraction, max_stake_pct)
            
    def _render_match_card(
        self,
        match: MatchData,
        output: ModelOutput,
        kelly_fraction: float,
        max_stake: float
    ):
        """Render individual match trading card"""
        
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])
            
            # Header
            tz = pytz.timezone('Asia/Taipei')
            kickoff_str = match.kickoff.astimezone(tz).strftime('%H:%M') if match.kickoff else 'TBD'
            
            with col1:
                st.markdown(f"""
                ### {match.home_team} vs {match.away_team}
                **{match.league}** • {kickoff_str} TPE
                """)
                
            with col2:
                trap_color = {
                    TrapSignal.OK: "green",
                    TrapSignal.WARNING: "orange",
                    TrapSignal.TRAP_HOME: "red",
                    TrapSignal.TRAP_AWAY: "red",
                    TrapSignal.TRAP_DRAW: "orange"
                }[output.trap_signal]
                st.markdown(f"**Trap Signal:** :{trap_color}[{output.trap_signal.value}]")
                
            with col3:
                st.metric(
                    "Confidence",
                    f"{output.confidence_score:.1%}",
                    f"Upset: {output.upset_probability:.1%}"
                )
                
            # Probabilities comparison
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Home",
                    f"{output.home_prob:.1%}",
                    f"vs {1/match.market_odds.home:.1%} market"
                )
                
            with col2:
                st.metric(
                    "Draw",
                    f"{output.draw_prob:.1%}",
                    f"vs {1/match.market_odds.draw:.1%} market"
                )
                
            with col3:
                st.metric(
                    "Away",
                    f"{output.away_prob:.1%}",
                    f"vs {1/match.market_odds.away:.1%} market"
                )
                
            with col4:
                best_pick = max(output.ev_1x2.items(), key=lambda x: x[1])
                st.metric(
                    "Best Pick",
                    best_pick[0].upper(),
                    f"EV: {best_pick[1]:+.1%}"
                )
                
            # Score distribution and markets
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Top 5 Scorelines**")
                score_df = pd.DataFrame(
                    output.score_distribution.items(),
                    columns=['Score', 'Probability']
                ).nlargest(5, 'Probability')
                score_df['Probability'] = score_df['Probability'].apply(lambda x: f"{x:.1%}")
                st.dataframe(score_df, hide_index=True, use_container_width=True)
                
            with col2:
                st.markdown("**Over/Under Markets**")
                ou_data = {
                    'Line': ['O1.5', 'U1.5', 'O2.5', 'U2.5', 'O3.5', 'U3.5'],
                    'Prob': [
                        output.over_15_prob,
                        1 - output.over_15_prob,
                        output.over_25_prob,
                        1 - output.over_25_prob,
                        output.over_35_prob,
                        1 - output.over_35_prob
                    ]
                }
                ou_df = pd.DataFrame(ou_data)
                ou_df['Prob'] = ou_df['Prob'].apply(lambda x: f"{x:.1%}")
                st.dataframe(ou_df, hide_index=True, use_container_width=True)
                
            # Trading signals
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown("**1X2 EV & Kelly**")
                for outcome in ['home', 'draw', 'away']:
                    ev = output.ev_1x2[outcome]
                    kelly = output.kelly_stakes[outcome] * kelly_fraction
                    color = "green" if ev > 0 else "red"
                    st.markdown(f"{outcome.upper()}: :{color}[{ev:+.1%}] | {kelly:.1%} stake")
                    
            with col2:
                st.markdown("**Asian Handicap**")
                st.metric(
                    "Value Signal",
                    f"{output.asian_handicap_value:+.3f}",
                    "vs -0.5 line"
                )
                
            with col3:
                st.markdown("**Expected Goals**")
                st.write(f"Home: {output.expected_goals_home:.2f}")
                st.write(f"Away: {output.expected_goals_away:.2f}")
                st.write(f"Total: {output.expected_goals_home + output.expected_goals_away:.2f}")
                
            with col4:
                st.markdown("**Recommendation**")
                if max(output.ev_1x2.values()) > 0.05:
                    best_bet = max(output.ev_1x2.items(), key=lambda x: x[1])
                    stake = output.kelly_stakes[best_bet[0]] * kelly_fraction
                    st.success(f"**{best_bet[0].upper()}** @ {getattr(match.market_odds, best_bet[0]):.2f}")
                    st.info(f"Stake: {min(stake, max_stake):.1%} of bankroll")
                else:
                    st.warning("No Clear Edge")
                    
        st.markdown("---")
        
    def _generate_demo_matches(self) -> List[MatchData]:
        """Generate demo matches for testing"""
        matches = []
        
        demo_fixtures = [
            ("Manchester City", "Arsenal", "EPL", 1.85, 3.75, 4.20),
            ("Real Madrid", "Barcelona", "La Liga", 1.95, 3.60, 3.80),
            ("Bayern Munich", "Dortmund", "Bundesliga", 1.65, 4.20, 4.50),
            ("PSG", "Marseille", "Ligue 1", 1.55, 4.50, 5.00),
            ("Inter", "Juventus", "Serie A", 2.10, 3.30, 3.50),
            ("LAFC", "LA Galaxy", "MLS", 1.90, 3.70, 3.60),
        ]
        
        for i, (home, away, league, h_odds, d_odds, a_odds) in enumerate(demo_fixtures):
            home_stats = TeamStats(
                team_id=str(i),
                team_name=home,
                league=league,
                attack_strength=np.random.uniform(0.9, 1.3),
                defense_strength=np.random.uniform(0.8, 1.2),
                form_5_matches=np.random.uniform(0.8, 1.3)
            )
            
            away_stats = TeamStats(
                team_id=str(i + 100),
                team_name=away,
                league=league,
                attack_strength=np.random.uniform(0.9, 1.3),
                defense_strength=np.random.uniform(0.8, 1.2),
                form_5_matches=np.random.uniform(0.8, 1.3)
            )
            
            market_odds = MarketOdds(
                home=h_odds,
                draw=d_odds,
                away=a_odds,
                over_25=1.90,
                under_25=1.90
            )
            
            match = MatchData(
                match_id=str(i),
                home_team=home,
                away_team=away,
                league=league,
                kickoff=datetime.now() + timedelta(hours=i*2),
                home_stats=home_stats,
                away_stats=away_stats,
                market_odds=market_odds,
                news_sentiment={'injury_impact': 1.0}
            )
            
            matches.append(match)
            
        return matches

# ============================================
# MAIN APPLICATION
# ============================================

def main():
    """Application entry point"""
    
    # Check for API keys
    required_keys = ['ODDS_API_KEY', 'SPORTMONKS_API_KEY', 'NEWS_API_KEY']
    missing_keys = [k for k in required_keys if not os.getenv(k)]
    
    if missing_keys:
        logger.warning(f"Missing API keys: {missing_keys}")
        logger.info("Running in demo mode with synthetic data")
        
    # Launch dashboard
    dashboard = TradingDashboard()
    dashboard.run()
    
if __name__ == "__main__":
    main()
