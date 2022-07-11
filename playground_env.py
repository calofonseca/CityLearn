from citylearn.citylearn import CityLearnEnv
# from gym.wrappers.monitoring.video_recorder import VideoRecorder
import cv2

if __name__ == '__main__':
    schema = './citylearn/data/citylearn_challenge_2022_phase_1/schema.json'
    env = CityLearnEnv(schema=schema)
    
    video_path='./videos/test_render.mp4'
    fourcc = cv2.VideoWriter_fourcc(*'mjpg')
    writer = cv2.VideoWriter(video_path, fourcc, 20, (720, 720))
    print("Citylearn environment created")
    for _ in range(1):
        all_obs = env.reset()
        num_buildings = len(env.buildings)
        done = False
        tsteps = 0
        while not done:
            actions = [action_space.sample() for action_space in env.action_space]
            frame = env.render()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            writer.write(frame)
            # video_recorder.capture_frame()
            all_obs, all_rew, done, all_info = env.step(actions)
            tsteps += 1
            if tsteps % 50 == 0:
                print(f"Time steps: {tsteps}")
        # video_recorder.close()
        # video_recorder.enabled = False
        print(f"Episode completed in {tsteps} time steps")

    writer.release()
