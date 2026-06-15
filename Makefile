.PHONY: feedback

feedback:
	uv run python visual_feedback_controller.py

feedback-cam:
	uv run python visual_feedback_controller.py --camera-a 0 --camera-b 1

feedback-tune:
	uv run python visual_feedback_controller.py --kp 0.8 --ki 0.05 --kd 0.1

server:
	uv run python server.py
