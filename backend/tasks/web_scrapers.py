from celery import shared_task
from typing import List, Dict, Any
from loguru import logger
import asyncio

from tasks import celery_app
from scrapers.web import WebScraper


@shared_task
def scrape_forum(config_name: str, disease_terms: List[str], 
                max_pages: int = 5, **kwargs) -> Dict[str, Any]:
    """
    Scrape a specific forum for disease-related posts
    
    Args:
        config_name: Name of the configuration file (e.g., 'healthunlocked')
        disease_terms: List of disease terms to search for
        max_pages: Maximum pages to scrape per term
        **kwargs: Additional options passed to scraper
    
    Returns:
        Dictionary with scraping results
    """
    logger.info(f"Starting forum scrape: {config_name} for terms: {disease_terms}")
    
    results = {
        "config_name": config_name,
        "disease_terms": disease_terms,
        "total_found": 0,
        "total_processed": 0,
        "errors": []
    }
    
    # Run async scraper in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(_scrape_forum_async(
            config_name, disease_terms, max_pages, results, **kwargs
        ))
    except Exception as e:
        logger.error(f"Fatal error in forum scraping: {e}")
        results["errors"].append({
            "error": str(e),
            "type": "fatal"
        })
    finally:
        loop.close()
    
    logger.info(f"Forum scrape completed: {results['total_processed']}/{results['total_found']} posts")
    return results


async def _scrape_forum_async(config_name: str, disease_terms: List[str],
                            max_pages: int, results: Dict[str, Any], **kwargs):
    """Async helper for forum scraping"""
    
    async with WebScraper(config_name) as scraper:
        for term in disease_terms:
            try:
                logger.info(f"Searching {config_name} for: {term}")
                
                # Search for posts
                posts = await scraper.search(term, max_pages=max_pages, **kwargs)
                results["total_found"] += len(posts)
                
                # Save each post
                for post in posts:
                    try:
                        # Extract document data
                        document, source_updated_at = scraper.extract_document_data(post)
                        
                        # Save to database
                        doc_id = await scraper.save_document(document, source_updated_at)
                        if doc_id:
                            results["total_processed"] += 1
                            
                            # Update source state for incremental
                            await scraper.update_source_state(
                                last_crawled_id=document.external_id
                            )
                        
                        # Progress update every 10 documents
                        if results["total_processed"] % 10 == 0:
                            logger.info(f"Progress: {results['total_processed']} posts saved")
                            
                    except Exception as e:
                        logger.error(f"Error processing post: {e}")
                        results["errors"].append({
                            "post_id": post.get('id', 'unknown'),
                            "error": str(e)
                        })
                        
            except Exception as e:
                logger.error(f"Error searching for '{term}': {e}")
                results["errors"].append({
                    "term": term,
                    "error": str(e)
                })


@shared_task
def scrape_all_forums(disease_terms: List[str], max_pages: int = 3) -> Dict[str, Any]:
    """
    Scrape all configured forums for disease terms
    
    Args:
        disease_terms: List of disease terms to search
        max_pages: Max pages per term per forum
        
    Returns:
        Combined results from all forums
    """
    forums = ["healthunlocked", "patient_info", "reddit_medical"]
    combined_results = {
        "disease_terms": disease_terms,
        "forums": {},
        "total_found": 0,
        "total_processed": 0
    }
    
    for forum in forums:
        try:
            result = scrape_forum(forum, disease_terms, max_pages)
            combined_results["forums"][forum] = result
            combined_results["total_found"] += result.get("total_found", 0)
            combined_results["total_processed"] += result.get("total_processed", 0)
        except Exception as e:
            logger.error(f"Failed to scrape {forum}: {e}")
            combined_results["forums"][forum] = {"error": str(e)}
    
    return combined_results


@shared_task
def scrape_forum_incremental(config_name: str, disease_terms: List[str] = None) -> Dict[str, Any]:
    """
    Run incremental update for a forum
    
    Args:
        config_name: Forum configuration name
        disease_terms: Optional list of terms, otherwise uses defaults
    
    Returns:
        Scraping results
    """
    # Default disease terms if not provided
    if not disease_terms:
        from core.config import settings
        disease_terms = settings.default_disease_terms[:5]  # Top 5 terms
    
    logger.info(f"Starting incremental update for {config_name}")
    
    # Get source state to determine how far back to go
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(_check_and_scrape_incremental(
            config_name, disease_terms
        ))
        return result
    finally:
        loop.close()


async def _check_and_scrape_incremental(config_name: str, disease_terms: List[str]) -> Dict[str, Any]:
    """Check source state and run appropriate scraping"""
    
    async with WebScraper(config_name) as scraper:
        # Get source state
        state = await scraper.get_source_state()
        last_crawled = state.get('last_crawled')
        
        if last_crawled:
            logger.info(f"Last crawled: {last_crawled}, running incremental")
            # For incremental, use fewer pages
            return await _scrape_forum_async(
                config_name, disease_terms, max_pages=2, 
                results={"total_found": 0, "total_processed": 0, "errors": []},
                since_date=last_crawled
            )
        else:
            logger.info("No previous crawl, running limited initial scrape")
            # Initial scrape with limited pages
            return await _scrape_forum_async(
                config_name, disease_terms, max_pages=3,
                results={"total_found": 0, "total_processed": 0, "errors": []}
            )


@shared_task
def test_forum_scraper(config_name: str, test_url: str = None) -> Dict[str, Any]:
    """
    Test a forum scraper configuration
    
    Args:
        config_name: Forum configuration to test
        test_url: Optional specific URL to test
        
    Returns:
        Test results including extracted data
    """
    logger.info(f"Testing forum scraper: {config_name}")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(_test_scraper(config_name, test_url))
        return result
    finally:
        loop.close()


async def _test_scraper(config_name: str, test_url: str = None) -> Dict[str, Any]:
    """Test scraper configuration"""
    
    test_results = {
        "config_name": config_name,
        "config_loaded": False,
        "page_fetched": False,
        "posts_found": 0,
        "sample_post": None,
        "errors": []
    }
    
    try:
        async with WebScraper(config_name) as scraper:
            test_results["config_loaded"] = True
            
            # Test search or specific URL
            if test_url:
                content = await scraper.fetch_page(test_url)
                test_results["page_fetched"] = bool(content)
                test_results["content_length"] = len(content)
            else:
                # Test search with a common term
                posts = await scraper.search("diabetes", max_pages=1)
                test_results["page_fetched"] = True
                test_results["posts_found"] = len(posts)
                
                if posts:
                    # Get first post as sample
                    test_results["sample_post"] = {
                        "title": posts[0].get("title", "")[:100],
                        "author": posts[0].get("author", ""),
                        "url": posts[0].get("url", ""),
                        "content_preview": posts[0].get("content", "")[:200],
                        "comments_count": len(posts[0].get("comments", []))
                    }
                    
    except Exception as e:
        test_results["errors"].append({
            "stage": "scraper_test",
            "error": str(e)
        })
    
    return test_results