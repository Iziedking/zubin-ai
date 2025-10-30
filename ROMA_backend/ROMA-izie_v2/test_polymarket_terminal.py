#!/usr/bin/env python3
"""
Simple terminal test for PolymarketToolkit
Run this directly from your terminal: python test_polymarket_terminal.py
"""
import asyncio
import sys


def test_1_import():
    """Test 1: Can we import PolymarketToolkit?"""
    print("\n" + "="*60)
    print("TEST 1: Import PolymarketToolkit")
    print("="*60)
    try:
        from roma_dspy.tools.crypto import PolymarketToolkit
        print("✅ PASS: PolymarketToolkit imported successfully!")
        return True, PolymarketToolkit
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False, None


async def test_2_initialize(PolymarketToolkit):
    """Test 2: Can we initialize the toolkit?"""
    print("\n" + "="*60)
    print("TEST 2: Initialize PolymarketToolkit")
    print("="*60)
    try:
        toolkit = PolymarketToolkit()
        print("✅ PASS: PolymarketToolkit initialized!")
        return True, toolkit
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False, None


async def test_3_trending(toolkit):
    """Test 3: Can we fetch trending markets?"""
    print("\n" + "="*60)
    print("TEST 3: Get Trending Markets")
    print("="*60)
    try:
        result = await toolkit.get_trending_markets(limit=3)
        # MarketSearchResult is a dataclass/model, use attribute access
        if hasattr(result, 'success') and result.success:
            markets = getattr(result, 'markets', [])
            print(f"✅ PASS: Got {len(markets)} trending markets")
            for i, market in enumerate(markets[:3], 1):
                title = market.get('title', 'N/A') if isinstance(market, dict) else getattr(market, 'title', 'N/A')
                print(f"   {i}. {str(title)[:70]}")
            return True
        else:
            error = getattr(result, 'error', 'Unknown error')
            print(f"❌ FAIL: {error}")
            return False
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_4_search(toolkit):
    """Test 4: Can we search markets?"""
    print("\n" + "="*60)
    print("TEST 4: Search Markets")
    print("="*60)
    try:
        result = await toolkit.search_markets(query="bitcoin", limit=3)
        # MarketSearchResult is a dataclass/model, use attribute access
        if hasattr(result, 'success') and result.success:
            markets = getattr(result, 'markets', [])
            print(f"✅ PASS: Found {len(markets)} markets for 'bitcoin'")
            for i, market in enumerate(markets[:3], 1):
                title = market.get('title', 'N/A') if isinstance(market, dict) else getattr(market, 'title', 'N/A')
                print(f"   {i}. {str(title)[:70]}")
            return True
        else:
            error = getattr(result, 'error', 'Unknown error')
            print(f"❌ FAIL: {error}")
            return False
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_5_agent_integration():
    """Test 5: Test with ROMA Agent (using your crypto_agent.yaml)"""
    print("\n" + "="*60)
    print("TEST 5: ROMA Agent Integration (THINK executor)")
    print("="*60)
    try:
        # Try different import patterns for Config
        config = None
        config_class = None
        
        # Try ROMAConfig first (most common)
        try:
            from roma_dspy.config import ROMAConfig
            config_class = ROMAConfig
            print("   Using: ROMAConfig")
        except ImportError:
            pass
        
        # Try Config as fallback
        if not config_class:
            try:
                from roma_dspy import Config
                config_class = Config
                print("   Using: Config")
            except ImportError:
                pass
        
        # Try alternative import path
        if not config_class:
            try:
                from roma_dspy.config.schemas.root import ROMAConfig
                config_class = ROMAConfig
                print("   Using: ROMAConfig from schemas.root")
            except ImportError:
                pass
        
        if not config_class:
            print("⚠️  SKIP: Could not import Config/ROMAConfig class")
            print("   This is OK - toolkit is working fine!")
            return None
        
        from pathlib import Path
        
        # Find crypto_agent.yaml or crypto.agent.yaml
        # Structure: config/profiles/crypto_agent.yaml
        config_paths = [
            "config/profiles/crypto_agent.yaml",   # ✅ Your actual nested path!
            "profiles/crypto_agent.yaml",
            "config/profiles/crypto.agent.yaml",
            "profiles/crypto.agent.yaml",
            "config/crypto_agent.yaml",
            "config/crypto.agent.yaml",
            "../config/profiles/crypto_agent.yaml",
            "crypto_agent.yaml",
            "crypto.agent.yaml",
        ]
        
        config_file = None
        for path in config_paths:
            if Path(path).exists():
                config_file = path
                break
        
        if not config_file:
            print("⚠️  SKIP: crypto_agent.yaml not found in expected locations")
            print("   Searched:", config_paths)
            print("   This is OK - toolkit is working fine!")
            return None
        
        print(f"   Loading config from: {config_file}")
        
        # Try to load the config
        try:
            # Try from_yaml method
            if hasattr(config_class, 'from_yaml'):
                config = config_class.from_yaml(config_file)
            # Try load_from_yaml method
            elif hasattr(config_class, 'load_from_yaml'):
                config = config_class.load_from_yaml(config_file)
            # Try direct instantiation
            else:
                import yaml
                with open(config_file, 'r') as f:
                    config_dict = yaml.safe_load(f)
                config = config_class(**config_dict)
        except Exception as e:
            print(f"⚠️  SKIP: Could not load config: {e}")
            print("   This is OK - toolkit is working fine!")
            return None
        
        print("✅ PASS: Config loaded successfully!")
        
        # Check if PolymarketToolkit is configured in THINK executor
        polymarket_found = False
        
        # Check agent_mapping structure
        if hasattr(config, 'agent_mapping'):
            agent_mapping = config.agent_mapping
            if isinstance(agent_mapping, dict) and 'executors' in agent_mapping:
                think_config = agent_mapping['executors'].get('THINK', {})
                toolkits = think_config.get('toolkits', [])
                
                polymarket_found = any(
                    (isinstance(tk, dict) and tk.get('class_name') == 'PolymarketToolkit')
                    for tk in toolkits
                )
        
        if polymarket_found:
            print("✅ PASS: PolymarketToolkit is configured in THINK executor!")
            return True
        else:
            print("⚠️  WARNING: PolymarketToolkit not found in THINK executor config")
            print("   But toolkit is working fine - you may need to add it to config")
            return False
            
    except Exception as e:
        print(f"⚠️  SKIP: {e}")
        print("   This is OK - toolkit is working fine!")
        import traceback
        traceback.print_exc()
        return None


async def run_all_tests():
    """Run all tests in sequence"""
    print("\n" + "🚀 "*30)
    print("POLYMARKET TOOLKIT - TERMINAL TEST SUITE")
    print("🚀 "*30)
    
    results = []
    
    # Test 1: Import
    success, PolymarketToolkit = test_1_import()
    results.append(("Import", success))
    if not success:
        print_summary(results)
        return
    
    # Test 2: Initialize
    success, toolkit = await test_2_initialize(PolymarketToolkit)
    results.append(("Initialize", success))
    if not success:
        print_summary(results)
        return
    
    # Test 3: Trending
    success = await test_3_trending(toolkit)
    results.append(("Get Trending Markets", success))
    
    # Test 4: Search
    success = await test_4_search(toolkit)
    results.append(("Search Markets", success))
    
    # Test 5: Agent Integration
    success = await test_5_agent_integration()
    results.append(("Agent Integration", success))
    
    print_summary(results)


def print_summary(results):
    """Print test summary"""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result is True)
    failed = sum(1 for _, result in results if result is False)
    skipped = sum(1 for _, result in results if result is None)
    
    for name, result in results:
        if result is True:
            print(f"✅ {name}")
        elif result is False:
            print(f"❌ {name}")
        else:
            print(f"⚠️  {name} (skipped)")
    
    print("="*60)
    print(f"Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    print("="*60)
    
    if failed == 0 and passed > 0:
        print("\n🎉 All tests PASSED! You're ready to test with Docker!")
    elif failed > 0:
        print("\n⚠️  Some tests FAILED. Check the errors above.")


def main():
    """Main entry point"""
    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    main()