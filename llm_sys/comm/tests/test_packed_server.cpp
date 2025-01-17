//
// Created by meiyixuan on 2024/4/15.
//
#include "../src/poller.h"
#include <thread>

int main(int argc, char *argv[]) {
    // get the port to work on
    if (argc < 4) {
        std::cerr << "Too few parameters! [example: packed_server 10.128.0.13 5555 1]\n";
        return 1;
    }
    std::string ip_str = argv[1];
    std::string port_str = argv[2];
    int server_id = std::stoi(argv[3]);
    auto address = "tcp://" + ip_str + ":" + port_str;

    // initialize context and polling server
    zmq::context_t context(1);
    PollServer server = PollServer(context, address);

    // send out messages
    int msg_id = 0;
    constexpr size_t buffer_size = 16 * 1024;
    std::vector<char> buffer(buffer_size, 'a');
    while (true) {
        // build header and buffer
        Header header = Header();
        header.msg_type = MsgType::Prompt;
        header.creation_time = get_time();
        header.add_stage(1, 0, 2);
        header.add_stage(2, 2, 4);
        header.request_id = server_id;
        zmq::message_t buffer_msg(buffer.data(), buffer.size());

        // send through zmq
        server.send(header, buffer_msg);

        // Sleep for demonstration purposes
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }

}