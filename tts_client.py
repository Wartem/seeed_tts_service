#!/usr/bin/env python3

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
import logging
from pathlib import Path

class TTSClient:
    def __init__(self, base_url: str = "http://localhost:8912"):
        self.base_url = base_url
        self.console = Console()
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self._setup_logging()
        self._session: Optional[aiohttp.ClientSession] = None
    
    def _setup_logging(self):
        logging.basicConfig(
            filename="tts_client.log",
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger("TTSClient")

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=10)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Make HTTP request"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            async with self._session.request(method, url, json=data) as response:
                response.raise_for_status()
                return await response.json()
                
        except Exception as e:
            self.logger.error(f"Request failed: {method} {endpoint} - {str(e)}")
            raise

    async def send_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Send text to be synthesized"""
        if not text.strip():
            self.console.print("[red]Error: Empty text not allowed[/red]")
            return None
            
        with Progress() as progress:
            task = progress.add_task("Sending text...", total=1)
            result = await self._make_request("POST", "/text", {"text": text})
            progress.update(task, completed=1)
            
        if result:
            self.logger.info(f"Text request sent successfully: {result['task_id']}")
        return result

    async def stop_playback(self) -> Optional[Dict[str, Any]]:
        return await self._make_request("POST", "/stop")

    async def get_status(self) -> Optional[Dict[str, Any]]:
        return await self._make_request("GET", "/status")

    def print_status(self, status: Dict[str, Any]):
        """Pretty print status"""
        table = Table(title="TTS Status")
        
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Currently Playing", str(status.get('currently_playing', 'None')))
        table.add_row("Queue Size", str(status.get('queue_size', 0)))
        
        self.console.print(table)
        
        if status.get('items'):
            items_table = Table(title="Queue Items")
            items_table.add_column("ID")
            items_table.add_column("Status")
            items_table.add_column("Queued At")
            
            for item in status['items']:
                items_table.add_row(
                    item['id'],
                    item['status'],
                    datetime.fromtimestamp(item['queued_at']).strftime('%H:%M:%S')
                )
            
            self.console.print(items_table)
            
async def main():
    async with TTSClient() as client:
        console = Console()
        
        while True:
            try:
                console.print("\n=== TTS Control Menu ===", style="bold blue")
                options = [
                    "1. Speak text",
                    "2. Stop playback",
                    "3. Show status",
                    "4. Exit"
                ]
                
                for option in options:
                    console.print(option)
                console.print("====================", style="bold blue")
                
                choice = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("\nEnter your choice (1-4): ").strip()
                )
                
                if choice == "1":
                    text = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: input("\nEnter text to speak: ").strip()
                    )
                    if text:
                        try:
                            result = await client.send_text(text)
                            if result:
                                console.print(f"\nQueued with task ID: {result['task_id']}", style="green")
                        except Exception as e:
                            console.print(f"\nError sending text: {str(e)}", style="red bold")
                
                elif choice == "2":
                    try:
                        result = await client.stop_playback()
                        if result:
                            console.print("\nPlayback stopped", style="red")
                    except Exception as e:
                        console.print(f"\nError stopping playback: {str(e)}", style="red bold")
                
                elif choice == "3":
                    try:
                        status = await client.get_status()
                        if status:
                            client.print_status(status)
                    except Exception as e:
                        console.print(f"\nError getting status: {str(e)}", style="red bold")
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: input("\nPress Enter to continue...")
                    )
                
                elif choice == "4":
                    console.print("\nExiting...", style="yellow")
                    break
                
                else:
                    console.print("\nInvalid choice. Please try again.", style="red")
                    
            except Exception as e:
                console.print(f"\nUnexpected error: {str(e)}", style="red bold")
                console.print("\nFull error details:", style="red")
                import traceback
                console.print(traceback.format_exc(), style="red")

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
        sys.exit(1)