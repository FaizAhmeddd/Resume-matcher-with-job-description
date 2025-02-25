from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Optional, Any
import logging
import traceback
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException as FastAPIHTTPException
from dotenv import load_dotenv
from ResumeMatchingWithAPI import evaluate_candidates_comprehensive

load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EvaluationRequest(BaseModel):
    job_id: int


class CandidateScore(BaseModel):
    candidate_id: int
    final_score: float


class StandardResponse(BaseModel):
    success: bool
    status: str
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


@app.post("/evaluate-candidates/{job_id}")
async def evaluate_candidates(job_id: int) -> StandardResponse:
    """
    Evaluate candidates for a specific job and return their scores.
    
    Args:
        job_id (int): The ID of the job for evaluation
        
    Returns:
        StandardResponse: Standardized response with evaluation results
    """
    try:
        # Get results from the evaluation function
        final_scores = evaluate_candidates_comprehensive(job_id)
        
        # Log the successful completion
        logger.info(f"Evaluation completed for job_id: {job_id}")
        
        # Sort candidates by final score (highest to lowest)
        sorted_scores = sorted(
            final_scores, key=lambda x: x["final_score"], reverse=True
        )
        
        return StandardResponse(
            success=True,
            status="success",
            data={
                "job_id": job_id,
                "candidates": sorted_scores,
                "total_candidates": len(sorted_scores),
            },
        )
    
    except FastAPIHTTPException as he:
        # Properly extract FastAPI HTTPException details
        status_code = he.status_code
        error_detail = he.detail
        
        # Log the error with proper details
        logger.error(f"HTTP Exception ({status_code}): {error_detail}")
        
        return StandardResponse(
            success=False,
            status="error",
            message=f"Evaluation process failed: {error_detail}"
        )
    except Exception as e:
        # Log the full error traceback
        logger.error(f"Error in evaluate_candidates: {str(e)}")
        logger.error(traceback.format_exc())
        
        return StandardResponse(
            success=False,
            status="error",
            message=f"Evaluation process failed: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn

    config = uvicorn.Config(app, host="0.0.0.0", port=8000, loop="asyncio")
    server = uvicorn.Server(config)
    server.run()