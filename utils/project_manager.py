# utils/project_manager.py
"""
Project Manager - Handles organization of generated files into project folders.
Supports archiving previous projects when new requests are made.
"""
import os
import shutil
import json
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class ProjectManager:
    """Manages project organization, archiving, and file storage."""
    
    def __init__(self, projects_root: Path):
        """
        Initialize the project manager.
        
        Args:
            projects_root: Root directory for all projects
        """
        self.projects_root = Path(projects_root)
        self.current_dir = self.projects_root / "current"
        self.archived_dir = self.projects_root / "archived"
        
        # Create directories if they don't exist
        self.projects_root.mkdir(parents=True, exist_ok=True)
        self.current_dir.mkdir(parents=True, exist_ok=True)
        self.archived_dir.mkdir(parents=True, exist_ok=True)
        
        # Load project metadata
        self.metadata_file = self.projects_root / "projects_metadata.json"
        self.metadata = self._load_metadata()
        
    def _load_metadata(self) -> Dict:
        """Load project metadata from JSON file."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading metadata: {e}")
                return {"current": None, "archived": []}
        return {"current": None, "archived": []}
    
    def _save_metadata(self):
        """Save project metadata to JSON file."""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
    
    def create_new_project(self, user_request: str) -> Dict:
        """
        Create a new project and archive the current one if it exists.
        
        Args:
            user_request: The user's request text to use as project name
            
        Returns:
            Dict with project info (name, path, timestamp)
        """
        # Archive current project if it exists
        if self.metadata["current"]:
            self.archive_current_project()
        
        # Generate project name from user request
        project_name = self._generate_project_name(user_request)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Clear current directory
        if self.current_dir.exists():
            shutil.rmtree(self.current_dir)
        self.current_dir.mkdir(parents=True, exist_ok=True)
        
        # Update metadata
        self.metadata["current"] = {
            "name": project_name,
            "request": user_request,
            "timestamp": timestamp,
            "path": str(self.current_dir),
            "files": []
        }
        self._save_metadata()
        
        logger.info(f"Created new project: {project_name}")
        return self.metadata["current"]
    
    def archive_current_project(self) -> Optional[str]:
        """
        Archive the current project to the archived directory.
        
        Returns:
            Path to archived project directory, or None if no current project
        """
        if not self.metadata["current"]:
            return None
        
        current_project = self.metadata["current"]
        project_name = current_project["name"]
        timestamp = current_project["timestamp"]
        
        # Create archived project directory
        archived_name = f"{project_name}_{timestamp}"
        archived_path = self.archived_dir / archived_name
        
        try:
            # Copy current directory to archived
            if self.current_dir.exists() and any(self.current_dir.iterdir()):
                shutil.copytree(self.current_dir, archived_path, dirs_exist_ok=True)
                
                # Update metadata
                archived_project = {
                    **current_project,
                    "archived_path": str(archived_path),
                    "archived_at": datetime.now().isoformat()
                }
                self.metadata["archived"].append(archived_project)
                self.metadata["current"] = None
                self._save_metadata()
                
                logger.info(f"Archived project: {project_name} to {archived_path}")
                return str(archived_path)
        except Exception as e:
            logger.error(f"Error archiving project: {e}")
            return None
    
    def save_file(self, file_path: str, content: str, is_current: bool = True) -> str:
        """
        Save a file to the appropriate project directory.
        
        Args:
            file_path: Relative file path (e.g., "src/main.py")
            content: File content
            is_current: Whether to save to current or archived project
            
        Returns:
            Full path to saved file
        """
        base_dir = self.current_dir if is_current else self.archived_dir
        full_path = base_dir / file_path
        
        # Create parent directories
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Update metadata if current project
            if is_current and self.metadata["current"]:
                if file_path not in self.metadata["current"]["files"]:
                    self.metadata["current"]["files"].append(file_path)
                    self._save_metadata()
            
            logger.info(f"Saved file: {full_path}")
            return str(full_path)
        except Exception as e:
            logger.error(f"Error saving file {file_path}: {e}")
            raise
    
    def get_current_files(self) -> List[Dict]:
        """
        Get list of files in current project with metadata.
        
        Returns:
            List of file dicts with path, name, size, modified time
        """
        files = []
        if not self.current_dir.exists():
            return files
        
        for file_path in self.current_dir.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(self.current_dir)
                files.append({
                    "path": str(rel_path).replace("\\", "/"),
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                })
        
        return files
    
    def get_archived_projects(self) -> List[Dict]:
        """
        Get list of all archived projects with metadata.
        
        Returns:
            List of archived project metadata dicts
        """
        return self.metadata.get("archived", [])
    
    def download_all_files(self, project_type: str = "current") -> str:
        """
        Create a ZIP archive of all files in a project.
        
        Args:
            project_type: "current" or project name for archived
            
        Returns:
            Path to created ZIP file
        """
        if project_type == "current":
            source_dir = self.current_dir
            project_name = self.metadata["current"]["name"] if self.metadata["current"] else "current_project"
        else:
            # Find archived project
            archived_project = next(
                (p for p in self.metadata["archived"] if p["name"] == project_type),
                None
            )
            if not archived_project:
                raise ValueError(f"Archived project not found: {project_type}")
            source_dir = Path(archived_project["archived_path"])
            project_name = project_type
        
        # Create ZIP file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = self.projects_root / f"{project_name}_{timestamp}.zip"
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in source_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(source_dir)
                        zipf.write(file_path, arcname)
            
            logger.info(f"Created ZIP archive: {zip_path}")
            return str(zip_path)
        except Exception as e:
            logger.error(f"Error creating ZIP archive: {e}")
            raise
    
    def _generate_project_name(self, user_request: str) -> str:
        """
        Generate a clean project name from user request.
        
        Args:
            user_request: The user's request text
            
        Returns:
            Clean project name suitable for folder name
        """
        # Take first 50 chars, clean special characters
        name = user_request[:50].lower()
        name = "".join(c if c.isalnum() or c in (' ', '_', '-') else '' for c in name)
        name = "_".join(name.split())  # Replace spaces with underscores
        name = name[:40]  # Limit length
        
        if not name:
            name = "project"
        
        return name
    
    def get_project_tree(self) -> Dict:
        """
        Get hierarchical file tree structure for UI display.
        
        Returns:
            Dict with current and archived projects in tree format
        """
        tree = {
            "current": {
                "name": self.metadata["current"]["name"] if self.metadata["current"] else "No Project",
                "files": self._build_file_tree(self.current_dir) if self.current_dir.exists() else []
            },
            "archived": []
        }
        
        # Add archived projects
        for project in self.metadata.get("archived", []):
            archived_path = Path(project["archived_path"])
            if archived_path.exists():
                tree["archived"].append({
                    "name": project["name"],
                    "timestamp": project["timestamp"],
                    "request": project.get("request", ""),
                    "files": self._build_file_tree(archived_path)
                })
        
        return tree
    
    def _build_file_tree(self, root_dir: Path) -> List[Dict]:
        """
        Build hierarchical file tree from directory.
        
        Args:
            root_dir: Root directory to scan
            
        Returns:
            List of file/folder dicts with children
        """
        tree = []
        
        if not root_dir.exists():
            return tree
        
        # Group by folders
        folders = {}
        files = []
        
        for item in root_dir.iterdir():
            if item.is_dir():
                folders[item.name] = item
            elif item.is_file():
                files.append({
                    "name": item.name,
                    "path": str(item.relative_to(root_dir)).replace("\\", "/"),
                    "type": "file",
                    "size": item.stat().st_size
                })
        
        # Add folders with their children
        for folder_name, folder_path in sorted(folders.items()):
            tree.append({
                "name": folder_name,
                "path": str(folder_path.relative_to(root_dir)).replace("\\", "/"),
                "type": "folder",
                "children": self._build_file_tree(folder_path)
            })
        
        # Add files
        tree.extend(sorted(files, key=lambda x: x["name"]))
        
        return tree
