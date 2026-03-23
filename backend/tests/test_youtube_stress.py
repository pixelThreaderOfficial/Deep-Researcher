import time
import concurrent.futures
import sys
import os

# Add the project root to sys.path so we can import from main
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main.src.utils.utilities import youtube_search, get_video_data, get_video_transcript

# Some sample search queries to get a healthy pool of videos
QUERIES = ["python programming", "world news", "technology 2024", "funny cats", "music videos"]

def get_video_pool(size=20):
    print(f"Fetching {size} videos for the test pool...")
    videos = []
    
    # Let's just use some common fallback videos if py_youtube search is unstable.
    # py_youtube returns objects with video ID usually, but we'll try to parse it.
    fallback = [
        "jNQXAC9IVRw", "dQw4w9WgXcQ", "M7lc1UVf-VE", "LXb3EKWsInQ", 
        "9bZkp7q19f0", "kffacxfA7G4", "dQw4w9WgXcQ", "kJQP7kiw5Fk",
        "JGwWNGJdvx8", "9bZkp7q19f0", "Wch3gJG2IG4", "Zi_XLOBDo_Y",
        "CevxZvSJLk8", "YQHsXMglC9A", "fJ9rUzIMcZQ", "V-_O7nl0Ii0",
        "bHQqvYy5KYo", "OPf0YbXqDm0", "L_jWHffIx5E", "uelHwf8o7_U"
    ]
    
    try:
        results = youtube_search("popular science")
        if isinstance(results, list):
            for res in results:
                vid = None
                if hasattr(res, 'id'):
                    vid = res.id
                elif isinstance(res, dict):
                    vid = res.get('id', res.get('videoId'))
                else:
                    vid = str(res) # Just in case it's a string
                
                if vid and len(vid) >= 11:
                    if len(vid) > 11: 
                        # just taking a heuristic if it returned a full URL
                        if 'v=' in vid:
                            vid = vid.split('v=')[1][:11]
                    if {'id': vid} not in videos:
                        videos.append({'id': vid})
    except Exception as e:
        print(f"Search API error (using fallback): {e}")

    while len(videos) < size:
        videos.append({'id': fallback[len(videos) % len(fallback)]})
        
    return videos[:size]

def test_single_video(video):
    vid = video['id']
    url = f"https://www.youtube.com/watch?v={vid}"
    
    metrics = {
        'id': vid,
        'url': url,
        'metadata_time': None,
        'metadata_success': False,
        'transcript_time': None,
        'transcript_success': False,
        'total_time': None,
        'metadata_error': None,
        'transcript_error': None
    }
    
    start_time = time.time()
    
    # 1. Test Metadata
    t0 = time.time()
    try:
        data = get_video_data(url)
        metrics['metadata_success'] = True if data else False
    except Exception as e:
        metrics['metadata_error'] = str(e)
    metrics['metadata_time'] = time.time() - t0
    
    # 2. Test Transcript
    t0 = time.time()
    try:
        transcript = get_video_transcript(vid)
        metrics['transcript_success'] = True if transcript else False
    except Exception as e:
        metrics['transcript_error'] = str(e)
    metrics['transcript_time'] = time.time() - t0
    
    metrics['total_time'] = time.time() - start_time
    
    return metrics

def run_stress_test(concurrency=5, total_requests=20):
    print(f"--- Starting YouTube Utility Stress Test ---")
    print(f"Concurrency level: {concurrency} threads")
    print(f"Total target requests: {total_requests}")
    
    videos = get_video_pool(total_requests)
    print(f"Prepared pool of {len(videos)} videos.")
    print("Running tasks...")
    
    start_overall = time.time()
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(test_single_video, v): v for v in videos}
        
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            try:
                res = future.result()
                results.append(res)
                status_meta = "OK" if res['metadata_success'] else "FAIL"
                status_trans = "OK" if res['transcript_success'] else "FAIL"
                
                print(f"[{i:02d}/{total_requests:02d}] {res['id']:15s} | "
                      f"Total: {res['total_time']:5.2f}s | "
                      f"Meta: {res['metadata_time']:5.2f}s ({status_meta}) | "
                      f"Trans: {res['transcript_time']:5.2f}s ({status_trans})")
                      
                if not res['metadata_success'] and res['metadata_error']:
                    print(f"    -> Meta Error: {res['metadata_error']}")
                if not res['transcript_success'] and res['transcript_error']:
                    print(f"    -> Trans Error: {res['transcript_error']}")
            except Exception as e:
                print(f"[{i:02d}/{total_requests:02d}] Task threw an exception: {e}")
                
    end_overall = time.time()
    total_elapsed = end_overall - start_overall
    
    # Statistics
    successful_meta = sum(1 for r in results if r.get('metadata_success'))
    successful_trans = sum(1 for r in results if r.get('transcript_success'))
    
    avg_meta_time = sum(r['metadata_time'] for r in results) / len(results) if results else 0
    avg_trans_time = sum(r['transcript_time'] for r in results) / len(results) if results else 0
    avg_total_time = sum(r['total_time'] for r in results) / len(results) if results else 0
    
    req_per_min = (len(results) / total_elapsed) * 60 if total_elapsed > 0 else 0
    
    print("\n" + "="*40)
    print("--- Stress Test Final Results ---")
    print("="*40)
    print(f"Total Targets Evaluated: {len(results)}")
    print(f"Total Time Elapsed:      {total_elapsed:.2f} seconds")
    print(f"Throughput:              {req_per_min:.2f} requests per minute")
    print(f"Metadata Success Rate:   {successful_meta}/{len(results)} ({(successful_meta/len(results)*100) if len(results) else 0:.1f}%)")
    print(f"Transcript Success Rate: {successful_trans}/{len(results)} ({(successful_trans/len(results)*100) if len(results) else 0:.1f}%)")
    print("-" * 40)
    print(f"Avg Metadata Latency:    {avg_meta_time:.2f} seconds")
    print(f"Avg Transcript Latency:  {avg_trans_time:.2f} seconds")
    print(f"Avg Total Latency/Req:   {avg_total_time:.2f} seconds")
    print("="*40)
    
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Stress test YouTube utilities")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent threads")
    parser.add_argument("--requests", type=int, default=10, help="Total number of requests to make")
    args = parser.parse_args()
    
    run_stress_test(concurrency=args.concurrency, total_requests=args.requests)

# for stress testing for 50 requests with 10 concurrency "uv run python backend/tests/test_youtube_stress.py --concurrency 10 --requests 50"
