"""
Analytics endpoints for aggregated data from the ETL pipeline.
Provides score distributions, pass rates, timelines, and group statistics.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List, Dict, Any
from datetime import date

from app.database import get_session
from app.models.item import ItemRecord
from app.models.interaction import InteractionLog
from app.models.learner import Learner

router = APIRouter(tags=["analytics"])


async def _find_lab_and_tasks(lab_code: str, db: AsyncSession):
    """
    Locate a lab by its identifier and retrieve all associated tasks.
    
    Args:
        lab_code: Lab identifier like 'lab-04'
        db: Database session
        
    Returns:
        Tuple of (lab_item, list_of_tasks, list_of_task_ids)
        
    Raises:
        HTTPException: If lab not found
    """
    # Convert 'lab-04' to searchable format
    if lab_code.startswith('lab-'):
        try:
            lab_number = int(lab_code.split('-')[1])
            lab_title_pattern = f"Lab {lab_number:02d}"
        except (IndexError, ValueError):
            lab_title_pattern = lab_code
    else:
        lab_title_pattern = lab_code
    
    # Query for the lab
    lab_query = select(ItemRecord).where(
        ItemRecord.type == "lab",
        ItemRecord.title.contains(lab_title_pattern)
    )
    lab_result = await db.exec(lab_query)
    lab = lab_result.first()
    
    if not lab:
        raise HTTPException(
            status_code=404, 
            detail=f"Laboratory '{lab_code}' not found in database"
        )
    
    # Get all tasks belonging to this lab
    tasks_query = select(ItemRecord).where(
        ItemRecord.type == "task",
        ItemRecord.parent_id == lab.id
    )
    tasks_result = await db.exec(tasks_query)
    tasks = tasks_result.all()
    task_ids = [t.id for t in tasks]
    
    return lab, tasks, task_ids


def _empty_score_buckets():
    """Return empty score distribution with all four buckets."""
    return [
        {"bucket": "0-25", "count": 0},
        {"bucket": "26-50", "count": 0},
        {"bucket": "51-75", "count": 0},
        {"bucket": "76-100", "count": 0}
    ]


@router.get("/scores")
async def get_score_distribution(
    lab: str = Query(..., description="Lab code (e.g., 'lab-04')"),
    db: AsyncSession = Depends(get_session)
):
    """
    Get score distribution histogram for a specific lab.
    
    Returns four score buckets with counts of student submissions
    that fall into each range.
    """
    try:
        # Find lab and its tasks
        _, _, task_ids = await _find_lab_and_tasks(lab, db)
        
        # Return empty buckets if no tasks found
        if not task_ids:
            return _empty_score_buckets()
        
        # Define bucket boundaries
        bucket_definitions = [
            ("0-25", InteractionLog.score <= 25),
            ("26-50", (InteractionLog.score > 25) & (InteractionLog.score <= 50)),
            ("51-75", (InteractionLog.score > 50) & (InteractionLog.score <= 75)),
            ("76-100", InteractionLog.score > 75)
        ]
        
        result = []
        for bucket_name, condition in bucket_definitions:
            # Count interactions matching this bucket
            count_query = select(func.count()).where(
                InteractionLog.item_id.in_(task_ids),
                InteractionLog.score.isnot(None),
                condition
            )
            count_result = await db.exec(count_query)
            count = count_result.one()
            
            result.append({
                "bucket": bucket_name,
                "count": count
            })
        
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        # Log error and return empty buckets
        print(f"Error in score distribution: {e}")
        return _empty_score_buckets()


@router.get("/pass-rates")
async def get_task_pass_rates(
    lab: str = Query(..., description="Lab code (e.g., 'lab-04')"),
    db: AsyncSession = Depends(get_session)
):
    """
    Get average scores and attempt counts for each task in a lab.
    
    Returns a list of tasks with their average score and total attempts.
    """
    try:
        # Find lab and its tasks
        _, tasks, task_ids = await _find_lab_and_tasks(lab, db)
        
        if not tasks:
            return []
        
        result = []
        for task in tasks:
            # Calculate average score for this task
            avg_query = select(func.avg(InteractionLog.score)).where(
                InteractionLog.item_id == task.id,
                InteractionLog.score.isnot(None)
            )
            avg_result = await db.exec(avg_query)
            avg_score = avg_result.one() or 0.0
            
            # Count total attempts for this task
            count_query = select(func.count()).where(
                InteractionLog.item_id == task.id
            )
            count_result = await db.exec(count_query)
            attempts = count_result.one() or 0
            
            result.append({
                "task": task.title,
                "avg_score": round(float(avg_score), 1),
                "attempts": attempts
            })
        
        # Sort alphabetically by task title
        result.sort(key=lambda x: x["task"])
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in pass rates: {e}")
        return []


@router.get("/timeline")
async def get_timeline(
    lab: str = Query(..., description="Lab code (e.g., 'lab-04')"),
    db: AsyncSession = Depends(get_session)
):
    """
    Get submission counts per day for a specific lab.
    
    Returns a chronological list of dates with submission counts.
    """
    try:
        # Find task IDs
        _, _, task_ids = await _find_lab_and_tasks(lab, db)
        
        if not task_ids:
            return []
        
        # Group submissions by date - ИСПРАВЛЕНО!
        timeline_query = select(
            func.date(InteractionLog.created_at).label("submission_date"),
            func.count().label("total_submissions")
        ).where(
            InteractionLog.item_id.in_(task_ids)
        ).group_by(
            func.date(InteractionLog.created_at)
        ).order_by(
            func.date(InteractionLog.created_at)
        )
        
        timeline_result = await db.exec(timeline_query)
        timeline_data = timeline_result.all()
        
        return [
            {"date": str(item.submission_date), "submissions": item.total_submissions}
            for item in timeline_data
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in timeline: {e}")
        return []

@router.get("/groups")
async def get_group_performance(
    lab: str = Query(..., description="Lab code (e.g., 'lab-04')"),
    db: AsyncSession = Depends(get_session)
):
    """
    Get performance metrics grouped by student study groups.
    
    Returns average score and unique student count per group.
    """
    try:
        # Find task IDs
        _, _, task_ids = await _find_lab_and_tasks(lab, db)
        
        if not task_ids:
            return []
        
        # Query group statistics
        groups_query = select(
            Learner.student_group,
            func.avg(InteractionLog.score).label("group_average"),
            func.count(func.distinct(Learner.id)).label("student_count")
        ).join(
            InteractionLog, Learner.id == InteractionLog.learner_id
        ).where(
            InteractionLog.item_id.in_(task_ids),
            InteractionLog.score.isnot(None),
            Learner.student_group.isnot(None),
            Learner.student_group != ""
        ).group_by(
            Learner.student_group
        ).order_by(
            Learner.student_group
        )
        
        groups_result = await db.exec(groups_query)
        groups_data = groups_result.all()
        
        return [
            {
                "group": item.student_group,
                "avg_score": round(float(item.group_average or 0), 1),
                "students": item.student_count or 0
            }
            for item in groups_data
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in group performance: {e}")
        return []