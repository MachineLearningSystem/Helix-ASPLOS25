# 2024.10.29 Yixuan Mei
from simulator.initial_layout.layout_synthesizer import LayoutMethod, LayoutSynthesizer
from simulator.event_simulator.cluster_simulator import ClusterSimulator, ModelName, SchedulingMethod, RequestPhase
from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder, OfflineRequestFeeder
from simulator.scheduler.global_maxflow.global_maxflow_scheduler import KVParameters, SchedulingMode


def simulate_maxflow_offline():
    """
    Scheduling method: Helix MaxFlow
    Request arrival pattern: offline
    """
    # ---------------------------------------- Initialization ---------------------------------------- #
    # load the model placement
    # cluster_file_path is "simulator_cluster_file_name" in layout_args
    machine_num_dict = {"A100": 4, "L4": 8, "T4": 12}
    layout_synthesizer = LayoutSynthesizer(
        complete_cluster_file_name="config/single24.ini",
        machine_profile_name="config/machine_profile.ini",
        model_name=ModelName.LLaMa70B,
        workspace_path="sim_files",
        layout_method=LayoutMethod.LoadExisting,
        machine_num_dict=machine_num_dict
    )
    layout_args = {
        "solution_file_name": "./layouts/ilp/ilp_sol.ini",
        "simulator_cluster_file_name": "./layouts/ilp/simulator_cluster.ini",
    }
    cluster_file_path = layout_synthesizer.synthesize(args=layout_args)

    # initialize the simulator and set scheduler as MaxFlow scheduler
    simulator = ClusterSimulator(model_name=ModelName.LLaMa70B, machine_num_dict=machine_num_dict)
    simulator.from_ini_file(config_file_name=cluster_file_path)
    scheduler_args = {
        "kv_param": KVParameters(expected_kv_hwm=0.85, expected_output_length_ratio=1),
        "scheduling_mode": SchedulingMode.Offline,  # offline
    }
    simulator.init_scheduler(scheduling_method=SchedulingMethod.MaxFlow, args=scheduler_args)
    simulator.init_query_manager()
    simulator.mark_as_ready()

    # load model placement and update scheduler
    finish_model_loading_time = layout_synthesizer.set_layout(simulator=simulator)
    simulator.update_scheduler()

    # print some status information
    print(f"Max compute throughput = {layout_synthesizer.layout_synthesizer.get_flow_upper_bound()}")
    print(f"Max flow = {simulator.scheduler.core.flow_graph.flow_value}")
    simulator.visualize_cluster(title="model_placement", save_path="./sim_files")

    # ------------------------------------------ Simulation ------------------------------------------ #
    # setup simulation and run
    warm_up, duration = 60, 600
    auto_test = OfflineRequestFeeder(initial_query_count=20, start_time=finish_model_loading_time,
                                     duration=warm_up + duration, stop_at_duration=True, feed_hwm=0.8, seed=0)
    auto_test.auto_simulate(simulator=simulator, watch_items=["all"], watch_interval=10)

    # ------------------------------------------- Analysis ------------------------------------------- #
    analysis_start_time = finish_model_loading_time + warm_up
    analysis_end_time = finish_model_loading_time + warm_up + duration

    # compute decode throughput
    # Note: 1. here, each request represent one iteration of an LLM query (either prompt or decode)
    #       2. RequestPhase.Initialization is for prompt, RequestPhase.Increment is for decode
    #       3. token_seq_length is the number of tokens processed in this iteration
    total_tokens = 0
    for request_uid, time_request in simulator.finished_requests.items():
        time, request = time_request
        if request.phase == RequestPhase.Initialization:
            continue
        if analysis_start_time <= time <= analysis_end_time:
            assert request.token_seq_length == 1, "Decode requests should have token_seq_length == 1!"
            total_tokens += request.token_seq_length
    decode_throughput = total_tokens / duration

    # compute prompt and decode latency
    sum_prompt_latency, sum_decode_latency = 0, 0
    valid_prompts, valid_decodes = 0, 0
    for request_uid, time_request in simulator.finished_requests.items():
        time, request = time_request
        if analysis_start_time <= time <= analysis_end_time:
            if request.phase == RequestPhase.Initialization:
                sum_prompt_latency += request.location_history[-1][1] - request.location_history[0][1]
                valid_prompts += 1
            elif request.phase == RequestPhase.Increment:
                sum_decode_latency += request.location_history[-1][1] - request.location_history[0][1]
                valid_decodes += 1
            else:
                assert False, "Found unknown requests phase!"
    avg_prompt_latency = sum_prompt_latency / valid_prompts
    avg_decode_latency = sum_decode_latency / valid_decodes

    # print and plot
    print(f"# ------------------------------------------------------------- #")
    print(f"Simulation Results (time range: {analysis_start_time}s - {analysis_end_time}s)")
    print(f"Avg decode speed: {decode_throughput:.1f} tokens/s")
    print(f"Avg prompt latency: {avg_prompt_latency:.3f}s")
    print(f"Avg decode latency: {avg_decode_latency:.3f}s")
    print(f"# ------------------------------------------------------------- #")
    simulator.plot_inference_speed(max_time=700, save_path="./sim_files/throughput.png")
    simulator.plot_request_latency(ignore_initialize=True, save_path="./sim_files/latency.png")


def main():
    """
    Finally, we can run the simulator to see how the model placement and request scheduling perform.
    """
    # Scheduling method: Helix MaxFlow
    # Request arrival pattern: offline
    simulate_maxflow_offline()


if __name__ == '__main__':
    main()