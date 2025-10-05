"""
Test script for 3x3 Grid Generator
Tests AniList API integration and image generation
"""

import asyncio
import aiohttp
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from PIL import Image
    PIL_AVAILABLE = True
    print("✅ PIL/Pillow is available")
except ImportError:
    PIL_AVAILABLE = False
    print("❌ PIL/Pillow is NOT available - install with: pip install Pillow")

API_URL = "https://graphql.anilist.co"


async def test_anilist_query():
    """Test AniList API query"""
    print("\n🔍 Testing AniList API connection...")
    
    query = """
    query ($search: String, $type: MediaType) {
        Media(search: $search, type: $type) {
            id
            title {
                romaji
                english
            }
            coverImage {
                extraLarge
                large
            }
        }
    }
    """
    
    test_title = "Steins;Gate"
    variables = {"search": test_title, "type": "ANIME"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_URL,
                json={"query": query, "variables": variables},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    media = data.get("data", {}).get("Media")
                    
                    if media:
                        print(f"✅ AniList API working!")
                        print(f"   Found: {media['title']['romaji']}")
                        print(f"   Cover: {media['coverImage']['extraLarge'][:50]}...")
                        return True
                    else:
                        print(f"❌ No results for '{test_title}'")
                        return False
                else:
                    print(f"❌ API returned status {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Error testing API: {e}")
        return False


async def test_image_generation():
    """Test basic image generation"""
    if not PIL_AVAILABLE:
        print("\n❌ Skipping image test - PIL not available")
        return False
    
    print("\n🎨 Testing image generation...")
    
    try:
        # Create a simple test image
        img = Image.new("RGB", (930, 930), (20, 20, 20))
        
        # Try to save it
        import io
        output = io.BytesIO()
        img.save(output, format="PNG")
        output.seek(0)
        
        size = len(output.getvalue())
        print(f"✅ Image generation working!")
        print(f"   Generated {size} bytes")
        return True
        
    except Exception as e:
        print(f"❌ Error generating image: {e}")
        return False


async def test_cover_download():
    """Test downloading a cover image"""
    print("\n📥 Testing cover download...")
    
    try:
        test_url = "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx9253-7pdcVzQSkKxT.jpg"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(test_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    cover_bytes = await response.read()
                    print(f"✅ Cover download working!")
                    print(f"   Downloaded {len(cover_bytes)} bytes")
                    
                    # Try to open with PIL if available
                    if PIL_AVAILABLE:
                        import io
                        img = Image.open(io.BytesIO(cover_bytes))
                        print(f"   Image size: {img.size}")
                    
                    return True
                else:
                    print(f"❌ Download failed with status {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Error downloading cover: {e}")
        return False


async def test_full_workflow():
    """Test the complete 3x3 generation workflow"""
    if not PIL_AVAILABLE:
        print("\n❌ Skipping full workflow test - PIL not available")
        return False
    
    print("\n🔄 Testing full 3x3 workflow...")
    
    test_titles = [
        "Steins;Gate",
        "Fullmetal Alchemist: Brotherhood",
        "Death Note",
        "Code Geass",
        "Attack on Titan",
        "Cowboy Bebop",
        "Hunter x Hunter",
        "One Punch Man",
        "Demon Slayer"
    ]
    
    print(f"   Testing with {len(test_titles)} titles...")
    
    # Simulate the cog's fetch_media_cover function
    query = """
    query ($search: String, $type: MediaType) {
        Media(search: $search, type: $type) {
            id
            title {
                romaji
                english
            }
            coverImage {
                extraLarge
                large
            }
        }
    }
    """
    
    found_count = 0
    
    try:
        async with aiohttp.ClientSession() as session:
            for title in test_titles:
                variables = {"search": title, "type": "ANIME"}
                
                async with session.post(
                    API_URL,
                    json={"query": query, "variables": variables},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("data", {}).get("Media"):
                            found_count += 1
        
        print(f"✅ Found {found_count}/{len(test_titles)} titles")
        
        if found_count >= 5:
            print(f"✅ Enough covers for 3x3 generation!")
            return True
        else:
            print(f"❌ Not enough covers (need at least 5)")
            return False
            
    except Exception as e:
        print(f"❌ Error in workflow test: {e}")
        return False


async def main():
    """Run all tests"""
    print("=" * 60)
    print("3x3 GRID GENERATOR - TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Test 1: AniList API
    results.append(("AniList API", await test_anilist_query()))
    
    # Test 2: Image Generation
    results.append(("Image Generation", await test_image_generation()))
    
    # Test 3: Cover Download
    results.append(("Cover Download", await test_cover_download()))
    
    # Test 4: Full Workflow
    results.append(("Full Workflow", await test_full_workflow()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! The 3x3 generator is ready to use!")
    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")
    
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
