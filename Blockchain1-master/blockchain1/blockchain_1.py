_auther_ = 'Harry'
_date_ = '5/22/2018 3:07 PM'

from time import time
import hashlib
import json
from flask import  Flask,jsonify,request
from uuid import uuid4
from urllib.parse import urlparse
import requests
from argparse import ArgumentParser


class Blockchain:

    def __init__(self):  #构造函数
        self.chain = []
        self.current_transactions = []
        self.nodes = set()  #set 里的节点都是独一无二的，和数组不一样
        self.new_block(proof=100,previous_hash=1) #这是第一个区块，所以工作量证明和前hash随意

    def register_node(self,address:str):  #注册节点
        # 地址的形式： https://127.0.0.1:5001
        parsed_url = urlparse(address) #解析url地址
        self.nodes.add(parsed_url.netloc)



    def valid_chain(self,chain) ->bool :

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain) :
            block = chain[current_index]

            if block['previous_hash'] != self.hash(last_block):
                # 上一个块的hash值 不对等
                return False

            if not self.valid_proof(last_block['proof'],block['proof']):
                #上一个块和当前块的工作量证明满足四个0开头
                return False

            last_block = block
            current_index +=1

        return True





    def resolve_conflicts(self) -> bool:
        """
        共识算法解决冲突
        使用网络中最长的链.

        :return:  如果链被取代返回 True, 否则为False
        """

        neighbours = self.nodes
        new_chain = None

        # We're only looking for chains longer than ours
        max_length = len(self.chain)

        # Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            self.chain = new_chain
            return True

        return False


    def new_block(self,proof,previous_hash=None): # 新添加一个块

        block = {
            'index':len(self.chain)+1,
            'timestamp':time(),
            'transactions':self.current_transactions,
            'proof':proof,
            'previous_hash':previous_hash or self.hash(self.last_block) #上一个区块的hash值
        }

        self.current_transactions=[]
        self.chain.append(block)

        return block


    def new_transaction(self,sender,recipient,amount):  #新添加交易
        # 把新的交易信息 加入到当前的交易信息中
        self.current_transactions.append(
            {
                'sender':sender,
                'recipient':recipient,
                'amount':amount
            }
        )

        return  self.last_block['index'] +1


    @staticmethod
    def hash(block):  # 计算区块的hash值
        block_string = json.dumps(block,sort_keys=True).encode() #输出json格式的string

        return hashlib.sha256(block_string).hexdigest() #返回hash后的摘要信息


    @property
    def last_block(self):  #区块的最后一个块 当作属性

        return self.chain[-1]



    def proof_of_work(self, last_prrof: int) ->int:
        proof = 0
        while self.valid_proof(last_prrof,proof) is False:
            proof += 1
        print(proof)
        return  proof


    def valid_proof(self,last_proof :int,proof: int) ->bool:
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        print(guess_hash)
        if guess_hash[0:4] == "0000":
            return  True
        else:
            return False

# testPow = Blockchain()
# testPow.proof_of_work(100)

blockchain = Blockchain() #实例化

node_identifier = str(uuid4()).replace('-', '')


app = Flask(__name__)
@app.route('/index',methods=['GET']) #定义路由,并映射一个方法
def index():
    return "Hello BlockChain"

@app.route('/transactions/new',methods=['POST'])
def new_transaction(): #新添交易
    values = request.get_json() #拿到客户post过来的内容
    required = ["sender","recipient","amount"]
    if values is None:
        return "Missing Values", 400
    if not all(k in values for k in required):
        return "Missing Values", 400

    index = blockchain.new_transaction(values['sender'],
                               values['recipient'],
                               values['amount'])
    response = {"message":f'Transaction will be added to Block 2'}
    return jsonify(response),201


@app.route('/mine',methods=['GET']) #挖矿
def mine():
    last_block = blockchain.last_block #上一个区块
    last_proof = last_block['proof'] #上一个区块的工作证明
    proof = blockchain.proof_of_work(last_block)

    blockchain.new_transaction(sender="0",
                               recipient=node_identifier,
                               amount=1
                               )
    block = blockchain.new_block(proof,None)

    response = {
        "message":"New Block Forged",
        "index":block['index'],
        "transactions":block['transactions'],
        "proof":block['proof'],
        "previous_hash":block['previous_hash']
    }

    return jsonify(response), 200


@app.route('/chain',methods=['GET'])
def full_chain(): #把当前区块链信息返回给请求者
    response = {
        'chain':blockchain.chain,
        'length':len(blockchain.chain)
    }
    return jsonify(response),200   #转换成字符串型



@app.route('/nodes/register',methods=['POST'])
def register_nodes():
    values = request.get_json()
    #获取请求的内容
    # {"nodes":["https://127.0.0.1:5001"]}
    nodes = values.get("nodes")

    if nodes is None:
        return "Error: please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    respnse = {
        "message":"New nodes hava been added",
        "total_nodes":list(blockchain.nodes)
    }

    return jsonify(respnse), 201



@app.route('/nodes/resolve',methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts() # 链条是否被取代了

    if replaced:
        response = {
            "message": "Our chain was replaced",
            "new_chain": blockchain.chain
        }

    else:
        response = {
            "message": "Our chain is authoritative",
            "chain": blockchain.chain
        }

    return jsonify(response), 200

if __name__ == '__main__':

    parse = ArgumentParser()
    # -p --port 5001
    parse.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parse.parse_args()  #解析
    port = args.port
    app.run(host='0.0.0.0',port=port)


