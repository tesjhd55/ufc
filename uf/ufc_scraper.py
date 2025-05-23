from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
import os

app = Flask(__name__)

def get_upcoming_events_url():
    url = 'https://www.ufc.com/events'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all event links on the page
        event_links = soup.find_all('a', href=lambda x: x and '/event/' in x)
        if event_links:
            # Get the first event link
            href = event_links[0].get('href')
            if href:
                return 'https://www.ufc.com' + href if href.startswith('/') else href
        return None
    except Exception as e:
        return None

def fetch_event_urls(start_url):
    if not start_url:
        return []
        
    visited_urls = set()
    all_urls = set()

    current_url = start_url
    while current_url:
        if current_url in visited_urls:
            break

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(current_url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            all_urls.add(current_url)
            visited_urls.add(current_url)

            pager = soup.find('div', class_='pager__nav')
            if pager:
                next_link = pager.find('a', class_='next')
                prev_link = pager.find('a', class_='previous')
                
                for link in [next_link, prev_link]:
                    if link:
                        href = link.get('href')
                        if href:
                            full_url = 'https://www.ufc.com' + href if href.startswith('/') else href
                            if full_url not in visited_urls:
                                all_urls.add(full_url)

                if next_link:
                    href = next_link.get('href')
                    if href:
                        current_url = 'https://www.ufc.com' + href if href.startswith('/') else href
                        if current_url in visited_urls:
                            break
                    else:
                        break
                else:
                    break

            time.sleep(1)
        except Exception as e:
            break

    return list(all_urls)

def extract_fighter_info(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    fights = []
    seen_fights = set()
    
    fight_blocks = soup.find_all('div', class_=lambda x: x and 'c-listing-fight' in x)
    
    for block in fight_blocks:
        fight_info = {}
        
        division = block.find('div', class_='c-listing-fight__class-text')
        fight_info['weight_division'] = division.text.strip() if division else ''
        
        fighter_names = block.find_all('div', class_='c-listing-fight__corner-name')
        if len(fighter_names) >= 2:
            fight_info['fighter1_name'] = fighter_names[0].text.strip()
            fight_info['fighter2_name'] = fighter_names[1].text.strip()
        else:
            continue
        
        fight_key = f"{fight_info['fighter1_name']}_vs_{fight_info['fighter2_name']}"
        if fight_key in seen_fights:
            continue
        seen_fights.add(fight_key)
        
        ranks = block.find_all('div', class_='c-listing-fight__corner-rank')
        fight_info['fighter1_rank'] = ranks[0].text.strip() if len(ranks) > 0 else ''
        fight_info['fighter2_rank'] = ranks[1].text.strip() if len(ranks) > 1 else ''
        
        countries = block.find_all('div', class_='c-listing-fight__corner-country')
        fight_info['fighter1_country'] = countries[0].text.strip() if len(countries) > 0 else ''
        fight_info['fighter2_country'] = countries[1].text.strip() if len(countries) > 1 else ''
        
        odds = block.find_all('span', class_='c-listing-fight__odds-amount')
        fight_info['fighter1_odds'] = odds[0].text.strip() if len(odds) > 0 else ''
        fight_info['fighter2_odds'] = odds[1].text.strip() if len(odds) > 1 else ''
        
        event_date = soup.find('div', class_='c-hero__headline-suffix')
        fight_info['event_date'] = event_date.text.strip() if event_date else ''
        
        if fight_info['fighter1_name'] and fight_info['fighter2_name']:
            fights.append(fight_info)
    
    return fights

@app.route('/api/events', methods=['GET'])
def get_events():
    start_url = get_upcoming_events_url()
    if not start_url:
        return jsonify({'error': 'Could not find any upcoming events'}), 404
        
    event_urls = fetch_event_urls(start_url)
    all_events_data = {}
    
    for url in event_urls:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            fights_data = extract_fighter_info(response.text)
            
            if fights_data:
                event_id = url.split('/')[-1]
                all_events_data[event_id] = fights_data
            
            time.sleep(1)
        except Exception as e:
            continue
    
    return jsonify(all_events_data)

@app.route('/api/event/<event_id>', methods=['GET'])
def get_event(event_id):
    url = f'https://www.ufc.com/event/{event_id}'
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        fights_data = extract_fighter_info(response.text)
        
        if fights_data:
            return jsonify({event_id: fights_data})
        return jsonify({'error': 'No fights found for this event'}), 404
    except Exception as e:
        return jsonify({'error': f'Failed to fetch event data: {str(e)}'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)