import requests
import json
from typing import Optional, Dict, Any, Union
import sys
import time
from datetime import datetime
import asyncio
import aiohttp
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
import backoff
from dataclasses import dataclass
import logging
from pathlib import Path

@dataclass
class ClientConfig:
    base_url: str = "http://localhost:8912"
    timeout: int = 10
    max_retries: int = 3
    log_file: str = "tts_client.log"

class TTSClient:
    def __init__(self, config: Optional[ClientConfig] = None):
        self.config = config or ClientConfig()
        self.console = Console()
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self._setup_logging()
        self._session: Optional[aiohttp.ClientSession] = None
    
    def _setup_logging(self):
        logging.basicConfig(
            filename=self.config.log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger("TTSClient")

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Make HTTP request with retry logic"""
        url = f"{self.config.base_url}/{endpoint.lstrip('/')}"
        
        try:
            async with self._session.request(method, url, json=data) as response:
                response.raise_for_status()
                return await response.json()
                
        except Exception as e:
            self.logger.error(f"Request failed: {method} {endpoint} - {str(e)}")
            raise

    async def send_tts_request(self, text: str, priority: bool = False) -> Optional[Dict[str, Any]]:
        """Send text to be synthesized with progress tracking"""
        if not text.strip():
            self.console.print("[red]Error: Empty text not allowed[/red]")
            return None
            
        with Progress() as progress:
            task = progress.add_task("Sending TTS request...", total=1)
            result = await self._make_request("POST", "/tts", {
                "text": text,
                "priority": priority
            })
            progress.update(task, completed=1)
            
        if result:
            self.logger.info(f"TTS request sent successfully: {result['task_id']}")
        return result

    async def pause_playback(self) -> Optional[Dict[str, Any]]:
        return await self._make_request("POST", "/pause")

    async def resume_playback(self) -> Optional[Dict[str, Any]]:
        return await self._make_request("POST", "/resume")

    async def stop_playback(self) -> Optional[Dict[str, Any]]:
        return await self._make_request("POST", "/stop")

    async def get_status(self) -> Optional[Dict[str, Any]]:
        return await self._make_request("GET", "/status")

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        return await self._make_request("GET", f"/status/{task_id}")

    async def get_metrics(self) -> Optional[Dict[str, Any]]:
        return await self._make_request("GET", "/metrics")

    def print_status(self, status: Dict[str, Any]):
        """Pretty print status using Rich tables"""
        table = Table(title="TTS Status")
        
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Currently Playing", str(status.get('currently_playing', 'None')))
        table.add_row("Priority Queue", str(status.get('priority_queue_size', 0)))
        table.add_row("Regular Queue", str(status.get('regular_queue_size', 0)))
        
        self.console.print(table)
        
        if status.get('items'):
            items_table = Table(title="Queued Items")
            items_table.add_column("ID")
            items_table.add_column("Text")
            items_table.add_column("Status")
            items_table.add_column("Queued At")
            items_table.add_column("Priority")
            
            for item in status['items']:
                items_table.add_row(
                    item['id'],
                    item['text'],
                    item['status'],
                    datetime.fromtimestamp(item['queued_at']).strftime('%H:%M:%S'),
                    str(item['priority'])
                )
            
            self.console.print(items_table)

    def print_metrics(self, metrics: Dict[str, Any]):
        """Pretty print metrics using Rich tables"""
        table = Table(title="System Metrics")
        
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        system = metrics.get('system_metrics', {})
        queue = metrics.get('queue_metrics', {})
        
        table.add_row("Uptime", f"{system.get('uptime_seconds', 0):.1f}s")
        table.add_row("CPU (current)", f"{system.get('cpu_current', 0):.1f}%")
        table.add_row("CPU (average)", f"{system.get('cpu_average', 0):.1f}%")
        table.add_row("Memory (current)", f"{system.get('memory_current', 0):.1f}%")
        table.add_row("Memory (average)", f"{system.get('memory_average', 0):.1f}%")
        table.add_row("Priority Queue", str(queue.get('priority_queue_size', 0)))
        table.add_row("Regular Queue", str(queue.get('regular_queue_size', 0)))
        table.add_row("Active Items", str(queue.get('active_items', 0)))
        
        self.console.print(table)

async def main():
    config = ClientConfig()
    async with TTSClient(config) as client:
        console = Console()
        
        while True:
            try:
                console.print("\n=== TTS Control Menu ===", style="bold blue")
                options = [
                    "1. Speak text",
                    "2. Pause playback",
                    "3. Resume playback",
                    "4. Stop playback",
                    "5. Show status",
                    "6. Show system metrics",
                    "7. Exit"
                ]
                
                for option in options:
                    console.print(option)
                console.print("====================", style="bold blue")
                
                choice = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("\nEnter your choice (1-7): ").strip()
                )
                
                if choice == "1":
                    text = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: input("\nEnter text to speak: ").strip()
                    )
                    if text:
                        priority = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: input("Priority? (y/N): ").strip().lower() == 'y'
                        )
                        try:
                            result = await client.send_tts_request(text, priority)
                            if result:
                                console.print(f"\nQueued with task ID: {result['task_id']}", style="green")
                        except Exception as e:
                            console.print(f"\nError sending TTS request: {str(e)}", style="red bold")
                            await asyncio.get_event_loop().run_in_executor(
                                None, lambda: input("\nPress Enter to continue...")
                            )
                            continue
                
                elif choice == "2":
                    try:
                        result = await client.pause_playback()
                        if result:
                            console.print("\nPlayback paused", style="yellow")
                    except Exception as e:
                        console.print(f"\nError pausing playback: {str(e)}", style="red bold")
                        await asyncio.get_event_loop().run_in_executor(
                            None, lambda: input("\nPress Enter to continue...")
                        )
                        continue
                
                elif choice == "3":
                    try:
                        result = await client.resume_playback()
                        if result:
                            console.print("\nPlayback resumed", style="green")
                    except Exception as e:
                        console.print(f"\nError resuming playback: {str(e)}", style="red bold")
                        await asyncio.get_event_loop().run_in_executor(
                            None, lambda: input("\nPress Enter to continue...")
                        )
                        continue
                
                elif choice == "4":
                    try:
                        result = await client.stop_playback()
                        if result:
                            console.print("\nPlayback stopped and queue cleared", style="red")
                    except Exception as e:
                        console.print(f"\nError stopping playback: {str(e)}", style="red bold")
                        await asyncio.get_event_loop().run_in_executor(
                            None, lambda: input("\nPress Enter to continue...")
                        )
                        continue
                
                elif choice == "5":
                    try:
                        status = await client.get_status()
                        if status:
                            client.print_status(status)
                    except Exception as e:
                        console.print(f"\nError getting status: {str(e)}", style="red bold")
                        await asyncio.get_event_loop().run_in_executor(
                            None, lambda: input("\nPress Enter to continue...")
                        )
                        continue
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: input("\nPress Enter to continue...")
                    )
                
                elif choice == "6":
                    try:
                        metrics = await client.get_metrics()
                        if metrics:
                            client.print_metrics(metrics)
                    except Exception as e:
                        console.print(f"\nError getting metrics: {str(e)}", style="red bold")
                        await asyncio.get_event_loop().run_in_executor(
                            None, lambda: input("\nPress Enter to continue...")
                        )
                        continue
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: input("\nPress Enter to continue...")
                    )
                
                elif choice == "7":
                    console.print("\nExiting...", style="yellow")
                    break
                
                else:
                    console.print("\nInvalid choice. Please try again.", style="red")
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: input("\nPress Enter to continue...")
                    )
                    
            except Exception as e:
                console.print(f"\nUnexpected error: {str(e)}", style="red bold")
                console.print("\nFull error details:", style="red")
                import traceback
                console.print(traceback.format_exc(), style="red")
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("\nPress Enter to continue...")
                )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        Console().print("\nExiting...", style="yellow")
        sys.exit(0)
    except Exception as e:
        console = Console()
        console.print(f"\nFatal error: {str(e)}", style="red bold")
        console.print("\nFull error details:", style="red")
        import traceback
        console.print(traceback.format_exc(), style="red")
        input("\nPress Enter to exit...")
        sys.exit(1)