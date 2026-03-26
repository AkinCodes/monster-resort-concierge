# -------------------------------------------------------------
# STRESS TEST SCRIPT
# -------------------------------------------------------------
# Purpose: This script is designed to test how much traffic (how many users or requests)
# the Monster Resort Concierge system can handle at once. It sends lots of messages to the system
# very quickly, just like if many people were using it at the same time.
#
# Importance: By running this test, we can find out if the system will slow down, break,
# or start blocking users when too many people use it. This helps us make sure the system
# is reliable and ready for real-world use.
#
# What it does: The script sends 100 chat messages to the system as fast as possible,
# using several "virtual users" at once. It measures how quickly the system responds,
# and whether it starts blocking requests (rate limiting) when overloaded.
#
# Who is this for? Anyone who wants to check if the system can handle a busy day at the resort!
# No technical knowledge is needed to understand the results: just look for how many requests
# succeeded, how many were blocked, and how fast the system responded.
# -------------------------------------------------------------


"""
Monster Resort Concierge - Advanced Stress Test
================================================================
Purpose: Test system capacity under load with realistic scenarios
Features:
- Progressive load testing (ramp up)
- Configurable timeouts for AI responses
- Detailed metrics and reporting
- Multiple test scenarios
- Session simulation
================================================================
"""
import requests
import time
import random
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Dict
from datetime import datetime
import json


# -------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------
@dataclass
class TestConfig:
    """Test configuration"""

    url: str = "http://localhost:8000/chat"
    api_key: str = os.environ.get("MRC_API_KEY", "your-api-key-here")

    # Test parameters
    num_requests: int = 100
    concurrency: int = 10
    num_sessions: int = 10  # Simulate different users

    # Timeout settings (AI responses can be slow!)
    request_timeout: int = 60  # 60 seconds for AI to respond
    connection_timeout: int = 10  # 10 seconds to establish connection

    # Progressive load testing
    use_ramp_up: bool = True
    ramp_up_steps: int = 3  # Gradually increase load

    # Test messages
    test_messages: List[str] = field(
        default_factory=lambda: [
            "What rooms are available?",
            "Tell me about the spa services",
            "I'd like to book the Vampire Suite",
            "What dining options do you have?",
            "What activities are available?",
            "Can you recommend something for families?",
            "What's included in the resort package?",
            "Tell me about the Full Moon Café",
            "I need help with a booking",
            "What makes your resort special?",
        ]
    )


# -------------------------------------------------------------
# RESULT TRACKING
# -------------------------------------------------------------
@dataclass
class RequestResult:
    """Individual request result"""

    request_id: int
    session_id: str
    status_code: int
    response_time: float
    success: bool
    error_message: str = ""
    response_length: int = 0


class TestResults:
    """Aggregate test results and statistics"""

    def __init__(self):
        self.results: List[RequestResult] = []
        self.start_time: float = 0
        self.end_time: float = 0

    def add(self, result: RequestResult):
        """Add a result"""
        self.results.append(result)

    def calculate_stats(self) -> Dict:
        """Calculate comprehensive statistics"""
        total = len(self.results)
        if total == 0:
            return {}

        success_results = [r for r in self.results if r.success]
        failed_results = [r for r in self.results if not r.success]

        success_count = len(success_results)
        response_times = [r.response_time for r in success_results]

        # Status code breakdown
        status_codes = {}
        for r in self.results:
            status_codes[r.status_code] = status_codes.get(r.status_code, 0) + 1

        # Calculate percentiles
        percentiles = {}
        if response_times:
            sorted_times = sorted(response_times)
            percentiles = {
                "p50": sorted_times[len(sorted_times) // 2],
                "p90": sorted_times[int(len(sorted_times) * 0.9)],
                "p95": sorted_times[int(len(sorted_times) * 0.95)],
                "p99": (
                    sorted_times[int(len(sorted_times) * 0.99)]
                    if len(sorted_times) > 10
                    else sorted_times[-1]
                ),
            }

        return {
            "total_requests": total,
            "successful": success_count,
            "failed": len(failed_results),
            "success_rate": (success_count / total * 100) if total > 0 else 0,
            "status_codes": status_codes,
            "response_times": {
                "min": min(response_times) if response_times else 0,
                "max": max(response_times) if response_times else 0,
                "avg": statistics.mean(response_times) if response_times else 0,
                "median": statistics.median(response_times) if response_times else 0,
                "stdev": (
                    statistics.stdev(response_times) if len(response_times) > 1 else 0
                ),
                **percentiles,
            },
            "duration": self.end_time - self.start_time,
            "requests_per_second": (
                total / (self.end_time - self.start_time)
                if self.end_time > self.start_time
                else 0
            ),
        }

    def print_summary(self):
        """Print detailed test summary"""
        stats = self.calculate_stats()

        print("\n" + "=" * 70)
        print("📊 STRESS TEST RESULTS")
        print("=" * 70)

        print(f"\n⏱️  Test Duration: {stats['duration']:.2f}s")
        print(f"📨 Total Requests: {stats['total_requests']}")
        print(f"✅ Successful: {stats['successful']} ({stats['success_rate']:.1f}%)")
        print(f"❌ Failed: {stats['failed']}")
        print(f"🚀 Throughput: {stats['requests_per_second']:.2f} req/s")

        print("\n📈 Status Code Breakdown:")
        for code, count in sorted(stats["status_codes"].items()):
            emoji = "✅" if code == 200 else "⚠️" if code == 429 else "❌"
            code_name = {
                200: "OK",
                429: "Rate Limited",
                500: "Server Error",
                504: "Timeout",
                0: "Connection Error",
            }.get(code, "Unknown")
            print(f"  {emoji} {code} ({code_name}): {count}")

        rt = stats["response_times"]
        if rt["avg"] > 0:
            print("\n⏱️  Response Time Statistics:")
            print(f"  Min:     {rt['min']:.2f}s")
            print(f"  Max:     {rt['max']:.2f}s")
            print(f"  Average: {rt['avg']:.2f}s")
            print(f"  Median:  {rt['median']:.2f}s")
            print(f"  StdDev:  {rt['stdev']:.2f}s")

            if "p50" in rt:
                print(f"\n  Percentiles:")
                print(f"    P50: {rt['p50']:.2f}s")
                print(f"    P90: {rt['p90']:.2f}s")
                print(f"    P95: {rt['p95']:.2f}s")
                print(f"    P99: {rt['p99']:.2f}s")

        # Performance assessment
        print("\n🎯 Performance Assessment:")
        if stats["success_rate"] >= 95:
            print("  ✅ EXCELLENT - System handling load well")
        elif stats["success_rate"] >= 80:
            print("  ⚠️  GOOD - Some issues under load")
        elif stats["success_rate"] >= 50:
            print("  ⚠️  FAIR - Significant performance degradation")
        else:
            print("  ❌ POOR - System struggling under load")

        if rt["avg"] > 0:
            if rt["avg"] < 5:
                print("  ✅ Response times excellent (<5s)")
            elif rt["avg"] < 15:
                print("  ⚠️  Response times acceptable (5-15s)")
            else:
                print("  ❌ Response times slow (>15s)")

        print("=" * 70 + "\n")


# -------------------------------------------------------------
# TEST EXECUTION
# -------------------------------------------------------------
class StressTest:
    """Main stress test orchestrator"""

    def __init__(self, config: TestConfig):
        self.config = config
        self.results = TestResults()
        self.session = requests.Session()  # Reuse connections

    def send_request(self, request_id: int) -> RequestResult:
        """Send a single chat request"""
        session_id = f"session-{random.randint(1, self.config.num_sessions)}"
        message = random.choice(self.config.test_messages)

        payload = {"message": message, "session_id": session_id}

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        start_time = time.time()

        try:
            response = self.session.post(
                self.config.url,
                json=payload,
                headers=headers,
                timeout=(self.config.connection_timeout, self.config.request_timeout),
            )

            elapsed = time.time() - start_time

            return RequestResult(
                request_id=request_id,
                session_id=session_id,
                status_code=response.status_code,
                response_time=elapsed,
                success=response.status_code == 200,
                response_length=len(response.text),
                error_message=(
                    "" if response.status_code == 200 else response.text[:100]
                ),
            )

        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            return RequestResult(
                request_id=request_id,
                session_id=session_id,
                status_code=504,
                response_time=elapsed,
                success=False,
                error_message=f"Request timed out after {elapsed:.1f}s",
            )

        except requests.exceptions.ConnectionError as e:
            elapsed = time.time() - start_time
            return RequestResult(
                request_id=request_id,
                session_id=session_id,
                status_code=0,
                response_time=elapsed,
                success=False,
                error_message=f"Connection error: {str(e)[:100]}",
            )

        except Exception as e:
            elapsed = time.time() - start_time
            return RequestResult(
                request_id=request_id,
                session_id=session_id,
                status_code=0,
                response_time=elapsed,
                success=False,
                error_message=f"Error: {str(e)[:100]}",
            )

    def run_batch(self, start_id: int, count: int, concurrency: int):
        """Run a batch of requests with specified concurrency"""
        print(f"\n🔄 Running batch: {count} requests, concurrency: {concurrency}")

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(self.send_request, start_id + i): i
                for i in range(count)
            }

            completed = 0
            for future in as_completed(futures):
                result = future.result()
                self.results.add(result)
                completed += 1

                # Progress indicator
                if completed % max(1, count // 10) == 0:
                    status_icon = "✅" if result.success else "❌"
                    print(
                        f"  {status_icon} Progress: {completed}/{count} "
                        f"({result.status_code}, {result.response_time:.2f}s)"
                    )

    def run(self):
        """Execute the stress test"""
        print("🚀 Monster Resort Concierge - Stress Test")
        print("=" * 70)
        print(f"Target URL: {self.config.url}")
        print(f"Total Requests: {self.config.num_requests}")
        print(f"Concurrency: {self.config.concurrency}")
        print(f"Sessions: {self.config.num_sessions}")
        print(f"Request Timeout: {self.config.request_timeout}s")
        print(f"Ramp Up: {'Enabled' if self.config.use_ramp_up else 'Disabled'}")
        print("=" * 70)

        self.results.start_time = time.time()

        if self.config.use_ramp_up:
            # Progressive load testing
            step_size = self.config.num_requests // self.config.ramp_up_steps
            concurrency_step = self.config.concurrency // self.config.ramp_up_steps

            for step in range(self.config.ramp_up_steps):
                step_concurrency = min(
                    (step + 1) * concurrency_step, self.config.concurrency
                )
                step_requests = step_size

                print(f"\n📊 Step {step + 1}/{self.config.ramp_up_steps}")
                self.run_batch(
                    start_id=step * step_size,
                    count=step_requests,
                    concurrency=step_concurrency,
                )

                # Brief pause between steps
                if step < self.config.ramp_up_steps - 1:
                    time.sleep(2)
        else:
            # Full load immediately
            self.run_batch(0, self.config.num_requests, self.config.concurrency)

        self.results.end_time = time.time()
        self.results.print_summary()

        # Save detailed results to file
        self.save_results()

    def save_results(self):
        """Save detailed results to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stress_test_results_{timestamp}.json"

        data = {
            "config": {
                "url": self.config.url,
                "num_requests": self.config.num_requests,
                "concurrency": self.config.concurrency,
                "timeout": self.config.request_timeout,
            },
            "statistics": self.results.calculate_stats(),
            "individual_results": [
                {
                    "id": r.request_id,
                    "session": r.session_id,
                    "status": r.status_code,
                    "time": round(r.response_time, 3),
                    "success": r.success,
                    "error": r.error_message if r.error_message else None,
                }
                for r in self.results.results
            ],
        }

        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

        print(f"📄 Detailed results saved to: {filename}")


# -------------------------------------------------------------
# MAIN EXECUTION
# -------------------------------------------------------------
if __name__ == "__main__":
    # Quick test configuration
    quick_config = TestConfig(num_requests=20, concurrency=5, use_ramp_up=False)

    # Full stress test configuration
    full_config = TestConfig(
        num_requests=100, concurrency=10, use_ramp_up=True, ramp_up_steps=3
    )

    # Extreme load test
    extreme_config = TestConfig(
        num_requests=500, concurrency=50, use_ramp_up=True, ramp_up_steps=5
    )

    # Choose your test
    print("Select test mode:")
    print("1. Quick Test (20 requests, 5 concurrent)")
    print("2. Standard Test (100 requests, 10 concurrent)")
    print("3. Extreme Test (500 requests, 50 concurrent)")

    choice = input("\nEnter choice (1-3) or press Enter for Standard: ").strip()

    if choice == "1":
        config = quick_config
    elif choice == "3":
        config = extreme_config
    else:
        config = full_config

    # Run the test
    test = StressTest(config)
    test.run()





# Ah, victory! There they are. It turns out the PDFs weren't missing; they were just 
# hiding in the `generated_pdfs` folder as specified in your `docker-compose.yml`.

# ### 🛠️ The Stress Test Success

# You've just confirmed a major win: your **asynchronous worker logic** actually works under pressure.

# * **Reliability:** Despite those 20-second response times, the system successfully 
# generated a unique receipt for every request—even the ones where the guest name was 
# just "Guest" or "draculatransylvaniacom".
# * **Persistence:** Your volume mapping `- ./generated_pdfs:/app/generated_pdfs` is working 
# perfectly, as these files have "leaked" out of the container and onto your Mac.

# ---

# ### 📊 Reaching "Full Capacity" in Grafana

# Now that we have confirmed the "Body" (PDFs) and the "Mind" (Agent), we need to 
# connect the **"Eyes" (Grafana)**. Since your `docker-compose.yml` has Grafana and Prometheus 
# ready to go, let's verify if the stress test results were recorded.

# 1. **Open Grafana:** Go to `http://localhost:3000`.
# 2. **Add Data Source:** Navigate to **Connections -> Data Sources** and add **Prometheus**.
# 3. **URL:** Use `http://prometheus:9090` (this is the internal Docker network name).
# 4. **The Goal:** We want to see a chart that looks exactly like your Stress Test—a sudden 
# spike of 20 requests with a high latency plateau.

# ---

# ### 🧛 Next Step: The "Vampire Audit"

# Pick one of those files—perhaps `receipt_445793c5_draculatransylvaniacom.pdf`—and open it.

# **Would you like me to help you verify if the math inside is correct?** Specifically, 
# check if the room rate from the **RAG Knowledge Base** was applied correctly to the 
# final total. If the math matches the "Resort Data," you have a 100% complete, production-ready RAG system.